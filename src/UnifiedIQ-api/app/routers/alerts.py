"""Natural-language alert routes."""

from __future__ import annotations

import sqlglot
from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.errors import BAD_REQUEST, SQL_INVALID, AppError
from app.models.domain import Alert, CurrentUser, Notification
from app.models.requests import CreateAlertRequest
from app.models.responses import AlertSpec
from app.prompts.alert_system import ALERT_SYSTEM

router = APIRouter(prefix="/api", tags=["alerts"])


@router.post("/alerts", response_model=Alert)
async def create_alert(
    body: CreateAlertRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> Alert:
    spec, _ = await state.llm.chat_structured(
        [
            {"role": "system", "content": ALERT_SYSTEM},
            {"role": "user", "content": body.question},
        ],
        response_model=AlertSpec,
    )
    if spec.reject_reason or not spec.metric_sql:
        raise AppError(
            BAD_REQUEST,
            spec.reject_reason or "Could not derive a monitorable metric.",
            status_code=422,
        )
    try:
        sqlglot.transpile(spec.metric_sql, read="databricks", write="databricks")
    except sqlglot.errors.ParseError as exc:
        raise AppError(SQL_INVALID, f"Alert SQL did not parse: {exc}", status_code=422) from exc

    return await state.alerts.create(user.email, body.question, spec)


@router.get("/alerts", response_model=list[Alert])
async def list_alerts(
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> list[Alert]:
    return await state.alerts.list(user.email)


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, bool]:
    await state.alerts.delete(user.email, alert_id)
    return {"deleted": True}


@router.post("/alerts/{alert_id}/run", response_model=Alert)
async def run_alert(
    alert_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> Alert:
    alert = await state.alerts.run_now(user.email, alert_id)
    if alert is None:
        raise AppError(BAD_REQUEST, "Alert not found", status_code=404)
    return alert


@router.get("/notifications", response_model=list[Notification])
async def notifications(
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> list[Notification]:
    return state.in_app.recent(user.email)
