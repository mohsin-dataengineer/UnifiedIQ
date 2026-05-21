"""User memory routes (Tier 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.models.domain import CurrentUser, UserMemory
from app.models.requests import CreateMemoryRequest

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[UserMemory])
async def list_memory(
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> list[UserMemory]:
    return await state.user_memory.list(user.email)


@router.post("", response_model=UserMemory)
async def create_memory(
    body: CreateMemoryRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> UserMemory:
    return await state.user_memory.create(user.email, body.value)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, bool]:
    await state.user_memory.delete(user.email, memory_id)
    return {"deleted": True}
