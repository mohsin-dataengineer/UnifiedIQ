"""Self-audit endpoint - re-derive an answer a second way and compare."""

from __future__ import annotations

import sqlglot
from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.errors import SQL_INVALID, AppError
from app.models.domain import CurrentUser, VerificationResult
from app.models.requests import VerifyRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/verify", response_model=VerificationResult)
async def verify(
    body: VerifyRequest,
    state: AppState = Depends(get_state),
    _user: CurrentUser = Depends(get_current_user),
) -> VerificationResult:
    try:
        sqlglot.transpile(body.original_sql, read="databricks", write="databricks")
    except sqlglot.errors.ParseError as exc:
        raise AppError(SQL_INVALID, f"Original SQL did not parse: {exc}", status_code=422) from exc
    return await state.verifier.verify(body.question, body.original_sql)
