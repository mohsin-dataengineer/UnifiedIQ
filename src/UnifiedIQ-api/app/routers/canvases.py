"""Canvas + Published-Dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.errors import BAD_REQUEST, AppError
from app.models.domain import Canvas, CurrentUser
from app.models.requests import CreateCanvasRequest, UpdateCanvasRequest

router = APIRouter(prefix="/api/canvases", tags=["canvases"])


@router.get("", response_model=list[Canvas])
async def list_canvases(
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> list[Canvas]:
    return await state.canvases.list(user.email)


@router.post("", response_model=Canvas)
async def create_canvas(
    body: CreateCanvasRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> Canvas:
    return await state.canvases.create(user.email, body.name)


@router.patch("/{canvas_id}", response_model=Canvas)
async def rename_canvas(
    canvas_id: str,
    body: UpdateCanvasRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> Canvas:
    updated = await state.canvases.rename(user.email, canvas_id, body.name)
    if updated is None:
        raise AppError(BAD_REQUEST, "Canvas not found", status_code=404)
    return updated


@router.delete("/{canvas_id}")
async def delete_canvas(
    canvas_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, bool]:
    # Drop the canvas row first; if that's allowed, cascade-delete its views.
    await state.canvases.delete(user.email, canvas_id)
    await state.views.delete_in_canvas(user.email, canvas_id)
    return {"deleted": True}


@router.post("/{canvas_id}/publish", response_model=Canvas)
async def publish_canvas(
    canvas_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> Canvas:
    source = await state.canvases.get(user.email, canvas_id)
    if source is None:
        raise AppError(BAD_REQUEST, "Canvas not found", status_code=404)
    views = await state.views.list(user.email, canvas_id=canvas_id)
    published = await state.canvases.create_published(user.email, source)
    await state.views.copy_for_publish(user.email, published.id, views)
    return published
