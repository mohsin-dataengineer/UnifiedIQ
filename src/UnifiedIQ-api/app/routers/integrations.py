"""Integration routes (Part 2.7)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.models.domain import CurrentUser, HealthStatus
from app.models.requests import IntegrationExecuteRequest

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("", response_model=list[HealthStatus])
async def list_integrations(
    state: AppState = Depends(get_state),
    _user: CurrentUser = Depends(get_current_user),
) -> list[HealthStatus]:
    out: list[HealthStatus] = []
    for name in state.registry.names():
        out.append(await state.registry.get(name).health())
    return out


@router.post("/{name}/execute")
async def execute_integration(
    name: str,
    body: IntegrationExecuteRequest,
    state: AppState = Depends(get_state),
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    integration = state.registry.get(name)
    ctx = await integration.authenticate(user_token=None)
    result = await integration.execute(body.action, body.params, ctx=ctx)
    return {"integration": name, "result": result}
