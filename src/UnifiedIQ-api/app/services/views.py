"""ViewsService - pinned dashboard views.

Persists chart/KPI specs in the warehouse (`user_views` table) and re-runs
the saved SQL on demand so conversations become durable dashboards.

Every view lives inside a Canvas (see `CanvasService`). A view whose
`canvas_id` resolves to a published canvas is immutable and is rejected for
PATCH/DELETE.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from app.config import Settings
from app.errors import FORBIDDEN, SQL_INVALID, AppError
from app.models.domain import UserView, ViewSpec
from app.services.canvases import CanvasService
from app.services.warehouse import WarehouseService

logger = logging.getLogger(__name__)


def _q(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _ts(dt: datetime) -> str:
    return f"TIMESTAMP '{dt.astimezone(UTC):%Y-%m-%d %H:%M:%S}'"


def _now() -> datetime:
    return datetime.now(UTC)


class ViewsService:
    def __init__(
        self,
        settings: Settings,
        warehouse: WarehouseService,
        canvases: CanvasService | None = None,
    ) -> None:
        self._settings = settings
        self._wh = warehouse
        self._canvases = canvases
        # Same catalog/schema as alerts; one app-owned table per concern.
        self._table = f"{settings.warehouse_catalog}.{settings.warehouse_schema}.user_views"

    def set_canvases(self, canvases: CanvasService) -> None:
        """Late-bind the CanvasService (avoids a circular construction)."""
        self._canvases = canvases

    async def ensure_table(self) -> None:
        await self._wh.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table} ("
            "view_id STRING, user_email STRING, name STRING, "
            "kind STRING, spec STRING, is_shared BOOLEAN, "
            "created_at TIMESTAMP, updated_at TIMESTAMP) USING DELTA"
        )

    def _row_to_view(self, r: dict) -> UserView:
        spec_dict = json.loads(r["spec"])
        return UserView(
            id=r["view_id"],
            user_email=r["user_email"],
            name=r["name"],
            kind=r.get("kind") or "chart",
            spec=ViewSpec.model_validate(spec_dict),
            is_shared=bool(r.get("is_shared")),
            created_at=r.get("created_at") or _now(),
            updated_at=r.get("updated_at") or _now(),
        )

    async def _assert_canvas_writable(self, user_email: str, canvas_id: str | None) -> None:
        """403 if the view's parent canvas is published."""
        if not canvas_id or self._canvases is None:
            return
        canvas = await self._canvases.get(user_email, canvas_id)
        if canvas is not None and canvas.status == "published":
            raise AppError(
                FORBIDDEN,
                "Published dashboards are immutable.",
                status_code=403,
            )

    async def create(
        self,
        user_email: str,
        name: str,
        spec: ViewSpec,
        *,
        kind: str = "chart",
    ) -> UserView:
        # Route to the user's default draft canvas when the caller didn't pick one.
        canvas_id = spec.canvas_id
        if not canvas_id and self._canvases is not None:
            default = await self._canvases.ensure_default(user_email)
            canvas_id = default.id
            spec = spec.model_copy(update={"canvas_id": canvas_id})
        await self._assert_canvas_writable(user_email, canvas_id)

        view = UserView(
            id=uuid.uuid4().hex,
            user_email=user_email,
            name=name,
            kind=kind,  # type: ignore[arg-type]
            spec=spec,
        )
        spec_json = json.dumps(spec.model_dump())
        await self._wh.execute(
            f"INSERT INTO {self._table} VALUES ("
            f"{_q(view.id)}, {_q(view.user_email)}, {_q(view.name)}, "
            f"{_q(view.kind)}, {_q(spec_json)}, "
            f"{str(view.is_shared).lower()}, "
            f"{_ts(view.created_at)}, {_ts(view.updated_at)})"
        )
        return view

    async def list(
        self,
        user_email: str,
        *,
        canvas_id: str | None = None,
    ) -> list[UserView]:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE user_email = {_q(user_email)} "
            "ORDER BY created_at DESC"
        )
        views = [self._row_to_view(r) for r in rows]
        if canvas_id is not None:
            views = [v for v in views if v.spec.canvas_id == canvas_id]
        return views

    async def get(self, user_email: str, view_id: str) -> UserView | None:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE view_id = {_q(view_id)} "
            f"AND user_email = {_q(user_email)}"
        )
        return self._row_to_view(rows[0]) if rows else None

    async def update(
        self,
        user_email: str,
        view_id: str,
        *,
        name: str | None = None,
        spec_patch: dict | None = None,
    ) -> UserView | None:
        existing = await self.get(user_email, view_id)
        if existing is None:
            return None
        await self._assert_canvas_writable(user_email, existing.spec.canvas_id)
        new_name = name if name is not None else existing.name
        merged_spec = existing.spec.model_dump()
        if spec_patch:
            for k, v in spec_patch.items():
                # canvas_id is fixed at create time; a patch can't move a view
                # between canvases (use publish to clone, not to relocate).
                if k == "canvas_id":
                    continue
                merged_spec[k] = v
        # Re-validate so a bad patch can't corrupt storage.
        spec = ViewSpec.model_validate(merged_spec)
        now = _now()
        await self._wh.execute(
            f"UPDATE {self._table} SET "
            f"name = {_q(new_name)}, "
            f"spec = {_q(json.dumps(spec.model_dump()))}, "
            f"updated_at = {_ts(now)} "
            f"WHERE view_id = {_q(view_id)} AND user_email = {_q(user_email)}"
        )
        return UserView(
            id=existing.id,
            user_email=existing.user_email,
            name=new_name,
            kind=existing.kind,
            spec=spec,
            is_shared=existing.is_shared,
            created_at=existing.created_at,
            updated_at=now,
        )

    async def delete(self, user_email: str, view_id: str) -> None:
        existing = await self.get(user_email, view_id)
        if existing is None:
            return
        await self._assert_canvas_writable(user_email, existing.spec.canvas_id)
        await self._wh.execute(
            f"DELETE FROM {self._table} WHERE view_id = {_q(view_id)} "
            f"AND user_email = {_q(user_email)}"
        )

    async def copy_for_publish(
        self,
        user_email: str,
        target_canvas_id: str,
        source_views: list[UserView],
    ) -> list[UserView]:
        """Duplicate every source view into `target_canvas_id` verbatim.

        Used by the publish flow; bypasses the writable-canvas check because
        the new canvas is `published` by design.
        """
        copies: list[UserView] = []
        for v in source_views:
            new_spec = v.spec.model_copy(update={"canvas_id": target_canvas_id})
            new_view = UserView(
                id=uuid.uuid4().hex,
                user_email=user_email,
                name=v.name,
                kind=v.kind,
                spec=new_spec,
                is_shared=v.is_shared,
                created_at=_now(),
                updated_at=_now(),
            )
            spec_json = json.dumps(new_view.spec.model_dump())
            await self._wh.execute(
                f"INSERT INTO {self._table} VALUES ("
                f"{_q(new_view.id)}, {_q(new_view.user_email)}, {_q(new_view.name)}, "
                f"{_q(new_view.kind)}, {_q(spec_json)}, "
                f"{str(new_view.is_shared).lower()}, "
                f"{_ts(new_view.created_at)}, {_ts(new_view.updated_at)})"
            )
            copies.append(new_view)
        return copies

    async def delete_in_canvas(self, user_email: str, canvas_id: str) -> None:
        """Cascade-delete every view that belongs to `canvas_id`. Used after
        a draft canvas is deleted. Skips the writable check — the caller
        already verified the canvas was a draft.
        """
        views = await self.list(user_email, canvas_id=canvas_id)
        for v in views:
            await self._wh.execute(
                f"DELETE FROM {self._table} WHERE view_id = {_q(v.id)} "
                f"AND user_email = {_q(user_email)}"
            )

    async def run(self, user_email: str, view_id: str) -> tuple[UserView, list[dict]] | None:
        view = await self.get(user_email, view_id)
        if view is None:
            return None
        # Read-only execution; defense in depth against destructive SQL.
        sql = view.spec.sql.strip().rstrip(";")
        if not sql.lower().lstrip().startswith(("select", "with")):
            raise AppError(SQL_INVALID, "View SQL must be a SELECT.", status_code=422)
        rows = await self._wh.execute(sql)
        return view, rows

    async def backfill_canvas_ids(self) -> None:
        """One-shot migration: assign orphan views to a default draft canvas.

        Idempotent — only touches rows whose `spec.canvas_id` is empty.
        Safe to call repeatedly from `ensure_table`-style startup hooks.
        """
        if self._canvases is None:
            return
        try:
            rows = await self._wh.execute(
                f"SELECT view_id, user_email, spec, name, kind, is_shared, "
                f"created_at, updated_at FROM {self._table}"
            )
        except Exception:
            logger.exception("backfill: could not list views; skipping")
            return

        # Group orphan view ids by user.
        per_user: dict[str, list[dict]] = {}
        for r in rows:
            try:
                spec = json.loads(r["spec"])
            except (TypeError, ValueError):
                continue
            if spec.get("canvas_id"):
                continue
            per_user.setdefault(r["user_email"], []).append({**r, "_spec": spec})

        for email, orphans in per_user.items():
            try:
                default = await self._canvases.ensure_default(email)
            except Exception:
                logger.exception("backfill: ensure_default failed for %s", email)
                continue
            for r in orphans:
                spec = r["_spec"]
                spec["canvas_id"] = default.id
                try:
                    await self._wh.execute(
                        f"UPDATE {self._table} SET spec = {_q(json.dumps(spec))} "
                        f"WHERE view_id = {_q(r['view_id'])} "
                        f"AND user_email = {_q(email)}"
                    )
                except Exception:
                    logger.exception("backfill: update failed for view %s", r["view_id"])
