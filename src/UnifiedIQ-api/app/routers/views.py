"""Pinned dashboard view routes (Phase: pin-to-dashboard)."""

from __future__ import annotations

from typing import Any

import sqlglot
from fastapi import APIRouter, Depends

from app.deps import AppState, get_current_user, get_state
from app.errors import BAD_REQUEST, SQL_INVALID, AppError
from app.models.domain import CurrentUser, UserView, ViewSpec
from app.models.requests import CreateViewRequest, UpdateViewRequest

router = APIRouter(prefix="/api/views", tags=["views"])


@router.post("", response_model=UserView)
async def create_view(
    body: CreateViewRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> UserView:
    try:
        sqlglot.transpile(body.sql, read="databricks", write="databricks")
    except sqlglot.errors.ParseError as exc:
        raise AppError(SQL_INVALID, f"View SQL did not parse: {exc}", status_code=422) from exc
    spec = ViewSpec(
        question=body.question,
        sql=body.sql,
        chart_config=body.chart_config,  # type: ignore[arg-type]
        default_view=body.default_view,
        canvas_id=body.canvas_id,
    )
    return await state.views.create(user.email, body.name, spec)


@router.get("", response_model=list[UserView])
async def list_views(
    canvas_id: str | None = None,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> list[UserView]:
    return await state.views.list(user.email, canvas_id=canvas_id)


@router.patch("/{view_id}", response_model=UserView)
async def update_view(
    view_id: str,
    body: UpdateViewRequest,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> UserView:
    updated = await state.views.update(user.email, view_id, name=body.name, spec_patch=body.spec)
    if updated is None:
        raise AppError(BAD_REQUEST, "View not found", status_code=404)
    return updated


@router.delete("/{view_id}")
async def delete_view(
    view_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, bool]:
    await state.views.delete(user.email, view_id)
    return {"deleted": True}


@router.post("/{view_id}/run")
async def run_view(
    view_id: str,
    state: AppState = Depends(get_state),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    result = await state.views.run(user.email, view_id)
    if result is None:
        raise AppError(BAD_REQUEST, "View not found", status_code=404)
    view, rows = result
    return {"view": view.model_dump(), "rows": rows}
