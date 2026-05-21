"""Chat endpoints: non-streaming JSON and SSE streaming.

The streaming endpoint emits only the fixed event vocabulary (Part 2.5) and
always terminates with `done` or `error` - never a half-open stream.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator

import sqlglot
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.deps import AppState, get_current_user, get_state
from app.errors import INTERNAL, SQL_INVALID, AppError
from app.models.domain import (
    ChartConfig,
    CurrentUser,
    SessionTurn,
    TelemetryEvent,
)
from app.models.requests import ChatRequest
from app.models.responses import ChatResponse, SQLGenerationResponse
from app.prompts.chat_system import SQL_GENERATION_SYSTEM
from app.sse import sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_SUMMARY_SYSTEM = (
    "Summarize the query result for the user in two or three sentences. "
    "Be precise and do not invent numbers."
)


def _validate_sql(sql: str) -> None:
    try:
        sqlglot.transpile(sql, read="databricks", write="databricks")
    except sqlglot.errors.ParseError as exc:
        raise AppError(SQL_INVALID, f"Generated SQL did not parse: {exc}", status_code=422) from exc


async def _build_messages(
    body: ChatRequest, state: AppState, user_email: str
) -> list[dict[str, str]]:
    # Memory tiers 1 + 4: schema grounding and per-user facts are injected
    # into the planner system message so the model stops inventing tables.
    schema_block = ""
    try:
        schema_block = await state.schema.context_block(body.question)
    except Exception:  # noqa: BLE001 - chat must work without schema
        schema_block = ""
    memory_block = await state.user_memory.context_block(user_email)

    system = SQL_GENERATION_SYSTEM
    if schema_block:
        system = f"{system}\n\n{schema_block}"
    if memory_block:
        system = f"{system}\n\n{memory_block}"
    return [
        {"role": "system", "content": system},
        *({"role": m.role, "content": m.content} for m in body.history),
        {"role": "user", "content": body.question},
    ]


def _summary_messages(question: str, rows: list[dict]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": f"Question: {question}\nRows (truncated): {rows[:20]}",
        },
    ]


_TEMPORAL = ("date", "month", "day", "year", "time", "quarter", "week")


def _suggest_chart(rows: list[dict]) -> ChartConfig:
    """Heuristic default chart from the result shape. The UI lets the user
    switch types, so this only picks a sensible starting point."""
    if not rows:
        return ChartConfig(type="none")
    cols = list(rows[0].keys())
    numeric = [
        c for c in cols if isinstance(rows[0][c], (int, float)) and not isinstance(rows[0][c], bool)
    ]
    categorical = [c for c in cols if c not in numeric]

    if len(rows) == 1 or not categorical or not numeric:
        # Single row or no category/measure split -> KPI/table in the UI.
        return ChartConfig(type="none")

    x = categorical[0]
    is_time = any(t in x.lower() for t in _TEMPORAL)
    return ChartConfig(
        type="line" if is_time else "bar",
        x=x,
        y=numeric,
        title=None,
    )


async def _record(
    state: AppState,
    *,
    session_id: str,
    interaction_id: str,
    user: CurrentUser,
    question: str,
    answer: str,
    intent: str,
    latency_ms: int,
) -> None:
    await state.sessions.append(
        SessionTurn(
            session_id=session_id,
            user_email=user.email,
            role="user",
            content=question,
            interaction_id=interaction_id,
        )
    )
    await state.sessions.append(
        SessionTurn(
            session_id=session_id,
            user_email=user.email,
            role="assistant",
            content=answer,
            interaction_id=interaction_id,
        )
    )
    await state.telemetry.log(
        TelemetryEvent(
            event_type="chat",
            user_email=user.email,
            request_id=interaction_id,
            latency_ms=latency_ms,
            metadata={"intent": intent},
        )
    )


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    started = time.perf_counter()
    interaction_id = uuid.uuid4().hex
    session_id = body.session_id or uuid.uuid4().hex

    plan, _completion = await state.llm.chat_structured(
        await _build_messages(body, state, user.email),
        response_model=SQLGenerationResponse,
    )

    rows: list[dict] = []
    if plan.intent == "reject":
        answer = plan.rejection_reason or "This question cannot be answered."
    elif plan.intent == "clarify":
        answer = plan.clarifying_question or "Could you clarify your question?"
    else:
        if not plan.sql:
            raise AppError(
                SQL_INVALID,
                "Model returned no SQL for a data request",
                status_code=422,
            )
        _validate_sql(plan.sql)
        rows = await state.warehouse.execute(plan.sql)
        answer = await state.llm.chat(_summary_messages(body.question, rows))

    latency_ms = int((time.perf_counter() - started) * 1000)
    await _record(
        state,
        session_id=session_id,
        interaction_id=interaction_id,
        user=user,
        question=body.question,
        answer=answer,
        intent=plan.intent,
        latency_ms=latency_ms,
    )

    return ChatResponse(
        interaction_id=interaction_id,
        session_id=session_id,
        intent=plan.intent,
        answer=answer,
        sql=plan.sql,
        chart_config=plan.chart_config,
        data=rows,
        assumptions=plan.assumptions,
    )


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    started = time.perf_counter()
    interaction_id = uuid.uuid4().hex
    session_id = body.session_id or uuid.uuid4().hex

    async def events() -> AsyncIterator[str]:
        try:
            yield sse(
                "thinking",
                {"step": "plan", "detail": "Analyzing the question"},
            )
            plan, _ = await state.llm.chat_structured(
                await _build_messages(body, state, user.email),
                response_model=SQLGenerationResponse,
            )

            rows: list[dict] = []
            if plan.intent in ("reject", "clarify"):
                answer = (
                    plan.rejection_reason
                    or plan.clarifying_question
                    or "This question cannot be answered."
                )
                yield sse("data", {"text": answer})
            else:
                if not plan.sql:
                    raise AppError(
                        SQL_INVALID,
                        "Model returned no SQL for a data request",
                        status_code=422,
                    )
                _validate_sql(plan.sql)
                yield sse(
                    "sql",
                    {"sql": plan.sql, "assumptions": plan.assumptions},
                )
                yield sse(
                    "thinking",
                    {"step": "query", "detail": "Running the query"},
                )
                rows = await state.warehouse.execute(plan.sql)
                # Always stream the result set so the UI can render a table,
                # KPI cards, and a switchable chart - not only when the model
                # asked for a chart. Stays within the fixed SSE vocabulary.
                chart_cfg = (
                    plan.chart_config
                    if (plan.chart_config and plan.chart_config.type != "none")
                    else _suggest_chart(rows)
                )
                yield sse(
                    "chart",
                    {
                        "chart_config": chart_cfg.model_dump(),
                        "data_snapshot": rows[:500],
                    },
                )
                yield sse(
                    "thinking",
                    {"step": "summarize", "detail": "Summarizing results"},
                )
                parts: list[str] = []
                async for token in state.llm.stream(_summary_messages(body.question, rows)):
                    parts.append(token)
                    yield sse("data", {"text": token})
                answer = "".join(parts)

            latency_ms = int((time.perf_counter() - started) * 1000)
            await _record(
                state,
                session_id=session_id,
                interaction_id=interaction_id,
                user=user,
                question=body.question,
                answer=answer,
                intent=plan.intent,
                latency_ms=latency_ms,
            )
            yield sse(
                "done",
                {
                    "interaction_id": interaction_id,
                    "metadata": {
                        "session_id": session_id,
                        "intent": plan.intent,
                        "latency_ms": latency_ms,
                    },
                },
            )
        except AppError as exc:
            yield sse("error", {"code": exc.code, "message": exc.message})
        except Exception:
            logger.exception("chat stream failed")
            yield sse(
                "error",
                {"code": INTERNAL, "message": "Internal error"},
            )

    return StreamingResponse(events(), media_type="text/event-stream")
