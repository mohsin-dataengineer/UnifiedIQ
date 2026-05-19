"""Liveness/readiness endpoint (Part 6.2)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query

from app.deps import AppState, get_current_user, get_state
from app.models.domain import CurrentUser
from app.models.responses import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


@router.get("/health", response_model=HealthResponse)
async def health(
    deep: bool = Query(default=False),
    state: AppState = Depends(get_state),
) -> HealthResponse:
    dependencies: dict[str, bool] = {}
    status: str = "ok"

    if deep:
        try:
            warehouse_ok = await asyncio.wait_for(state.warehouse.health(), timeout=5.0)
        except (TimeoutError, Exception):  # noqa: BLE001 - health is best-effort
            warehouse_ok = False
        dependencies["warehouse"] = warehouse_ok
        if not warehouse_ok:
            status = "degraded"

    return HealthResponse(
        status=status,  # type: ignore[arg-type]
        version="0.1.0",
        git_sha=state.settings.git_sha,
        dependencies=dependencies,
    )
