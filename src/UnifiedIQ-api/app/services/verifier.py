"""VerifierService - self-auditing answers.

Asks the LLM to derive an INDEPENDENT alternative SQL that computes the
same metric a different way, executes both, and compares the results.

For single-numeric answers the verdict comes from a relative-tolerance
numeric compare. When the result isn't a scalar (e.g. a series), the
LLM-as-judge fallback is invoked. The judge call is also exposed as
`llm_judge()` so the eval harness can reuse it (closing the loop).
"""

from __future__ import annotations

import logging
from typing import Any

import sqlglot

from app.errors import LLM_INVALID_OUTPUT, SQL_INVALID, AppError
from app.models.domain import VerificationResult
from app.models.responses import AlternativeSQLResponse, JudgeScore
from app.prompts.judge_system import JUDGE_SYSTEM
from app.prompts.verifier_system import ALTERNATIVE_SQL_SYSTEM
from app.services.llm import LLMService
from app.services.warehouse import WarehouseService

logger = logging.getLogger(__name__)

_AGREE_TIGHT = 0.01  # within 1% -> high-confidence agree
_AGREE_LOOSE = 0.05  # within 5% -> agree at lower confidence
_DISAGREE_LOOSE = 0.20  # beyond 20% -> firm disagree


def extract_scalar(rows: list[dict[str, Any]]) -> float | None:
    """Pull a single numeric scalar from a result set, or None."""
    if not rows:
        return None
    first = rows[0]
    for v in first.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _compare(a: float, b: float) -> tuple[str, float, float]:
    """Return (verdict, confidence, diff_pct) for two scalars."""
    if a == 0 and b == 0:
        return "agree", 0.99, 0.0
    denom = max(abs(a), abs(b), 1e-9)
    diff = abs(a - b) / denom
    if diff <= _AGREE_TIGHT:
        return "agree", 0.98, diff
    if diff <= _AGREE_LOOSE:
        return "agree", 0.85, diff
    if diff <= _DISAGREE_LOOSE:
        return "inconclusive", 0.55, diff
    return "disagree", 0.1, diff


def _validate_sql(sql: str) -> None:
    try:
        sqlglot.transpile(sql, read="databricks", write="databricks")
    except sqlglot.errors.ParseError as exc:
        raise AppError(
            SQL_INVALID,
            f"Alternative SQL did not parse: {exc}",
            status_code=422,
        ) from exc


async def llm_judge(
    llm: LLMService,
    question: str,
    original_sql: str,
    original_rows: list[dict[str, Any]],
    alternative_sql: str,
    alternative_rows: list[dict[str, Any]],
) -> JudgeScore:
    """Reusable LLM-as-judge. Returned `confidence` is the judge's confidence
    in its verdict, not in either underlying answer."""
    user = (
        f"Question: {question}\n\n"
        f"Original SQL:\n{original_sql}\n"
        f"Original rows (first 10): {original_rows[:10]}\n\n"
        f"Alternative SQL:\n{alternative_sql}\n"
        f"Alternative rows (first 10): {alternative_rows[:10]}"
    )
    try:
        score, _ = await llm.chat_structured(
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_model=JudgeScore,
        )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize to stable code
        logger.exception("llm judge call failed")
        raise AppError(
            LLM_INVALID_OUTPUT,
            "Judge did not return a valid score",
            status_code=502,
        ) from exc
    return score


class VerifierService:
    def __init__(self, llm: LLMService, warehouse: WarehouseService) -> None:
        self._llm = llm
        self._wh = warehouse

    async def verify(self, question: str, original_sql: str) -> VerificationResult:
        # 1. Ask LLM for an independent alternative SQL.
        spec, _ = await self._llm.chat_structured(
            [
                {"role": "system", "content": ALTERNATIVE_SQL_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\nOriginal SQL (already executed):\n{original_sql}"
                    ),
                },
            ],
            response_model=AlternativeSQLResponse,
        )
        if spec.reject_reason or not spec.alternative_sql:
            return VerificationResult(
                verdict="inconclusive",
                confidence=0.0,
                alternative_sql="",
                alternative_approach="",
                rationale=spec.reject_reason or "Could not derive an independent alternative.",
            )

        _validate_sql(spec.alternative_sql)
        if spec.alternative_sql.strip() == original_sql.strip():
            return VerificationResult(
                verdict="inconclusive",
                confidence=0.0,
                alternative_sql=spec.alternative_sql,
                alternative_approach=spec.approach,
                rationale="Alternative SQL was identical to the original.",
            )

        # 2. Run both queries.
        original_rows = await self._wh.execute(original_sql)
        alternative_rows = await self._wh.execute(spec.alternative_sql)

        # 3. Numeric compare first; fall back to LLM judge when not scalar.
        a = extract_scalar(original_rows)
        b = extract_scalar(alternative_rows)
        if a is not None and b is not None:
            verdict, conf, diff = _compare(a, b)
            rationale = (
                f"Original metric ≈ {a:g}; alternative ≈ {b:g} (relative diff {diff * 100:.2f}%)."
            )
            return VerificationResult(
                verdict=verdict,  # type: ignore[arg-type]
                confidence=conf,
                original_value=a,
                alternative_value=b,
                alternative_sql=spec.alternative_sql,
                alternative_approach=spec.approach,
                rationale=rationale,
                diff_pct=diff,
            )

        # Non-scalar results -> judge.
        score = await llm_judge(
            self._llm,
            question,
            original_sql,
            original_rows,
            spec.alternative_sql,
            alternative_rows,
        )
        return VerificationResult(
            verdict=score.verdict,
            confidence=score.confidence,
            original_value=a,
            alternative_value=b,
            alternative_sql=spec.alternative_sql,
            alternative_approach=spec.approach,
            rationale=score.rationale,
        )
