"""CanvasService - draft canvases + published immutable snapshots.

A canvas groups pinned UserViews. `draft` canvases are mutable; `published`
canvases are read-only snapshots produced via `publish`. Publishing creates a
new canvas (status=published, source_canvas_id=<draft>) plus deep copies of
every view in the draft. The draft stays editable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.config import Settings
from app.errors import FORBIDDEN, AppError
from app.models.domain import Canvas
from app.services.warehouse import WarehouseService

logger = logging.getLogger(__name__)

DEFAULT_CANVAS_NAME = "My canvas"


def _q(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _ts(dt: datetime) -> str:
    return f"TIMESTAMP '{dt.astimezone(UTC):%Y-%m-%d %H:%M:%S}'"


def _now() -> datetime:
    return datetime.now(UTC)


class CanvasService:
    def __init__(self, settings: Settings, warehouse: WarehouseService) -> None:
        self._settings = settings
        self._wh = warehouse
        self._table = f"{settings.warehouse_catalog}.{settings.warehouse_schema}.user_canvases"

    async def ensure_table(self) -> None:
        await self._wh.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table} ("
            "canvas_id STRING, user_email STRING, name STRING, status STRING, "
            "source_canvas_id STRING, created_at TIMESTAMP, updated_at TIMESTAMP"
            ") USING DELTA"
        )

    def _row_to_canvas(self, r: dict) -> Canvas:
        return Canvas(
            id=r["canvas_id"],
            user_email=r["user_email"],
            name=r["name"],
            status=r.get("status") or "draft",  # type: ignore[arg-type]
            source_canvas_id=r.get("source_canvas_id"),
            created_at=r.get("created_at") or _now(),
            updated_at=r.get("updated_at") or _now(),
        )

    async def _insert(self, c: Canvas) -> None:
        await self._wh.execute(
            f"INSERT INTO {self._table} VALUES ("
            f"{_q(c.id)}, {_q(c.user_email)}, {_q(c.name)}, "
            f"{_q(c.status)}, {_q(c.source_canvas_id)}, "
            f"{_ts(c.created_at)}, {_ts(c.updated_at)})"
        )

    async def create(self, user_email: str, name: str) -> Canvas:
        c = Canvas(id=uuid.uuid4().hex, user_email=user_email, name=name)
        await self._insert(c)
        return c

    async def list(self, user_email: str) -> list[Canvas]:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE user_email = {_q(user_email)} "
            "ORDER BY created_at DESC"
        )
        return [self._row_to_canvas(r) for r in rows]

    async def get(self, user_email: str, canvas_id: str) -> Canvas | None:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE canvas_id = {_q(canvas_id)} "
            f"AND user_email = {_q(user_email)}"
        )
        return self._row_to_canvas(rows[0]) if rows else None

    async def rename(self, user_email: str, canvas_id: str, name: str) -> Canvas | None:
        existing = await self.get(user_email, canvas_id)
        if existing is None:
            return None
        if existing.status == "published":
            raise AppError(
                FORBIDDEN,
                "Published dashboards are immutable.",
                status_code=403,
            )
        now = _now()
        await self._wh.execute(
            f"UPDATE {self._table} SET name = {_q(name)}, updated_at = {_ts(now)} "
            f"WHERE canvas_id = {_q(canvas_id)} AND user_email = {_q(user_email)}"
        )
        return Canvas(
            id=existing.id,
            user_email=existing.user_email,
            name=name,
            status=existing.status,
            source_canvas_id=existing.source_canvas_id,
            created_at=existing.created_at,
            updated_at=now,
        )

    async def delete(self, user_email: str, canvas_id: str) -> None:
        """Delete the canvas row only. The router cascades view deletion via
        `ViewsService.delete_in_canvas` (keeps storage of each kind in its
        own service).
        """
        existing = await self.get(user_email, canvas_id)
        if existing is None:
            return
        if existing.status == "published":
            raise AppError(
                FORBIDDEN,
                "Published dashboards are immutable.",
                status_code=403,
            )
        await self._wh.execute(
            f"DELETE FROM {self._table} WHERE canvas_id = {_q(canvas_id)} "
            f"AND user_email = {_q(user_email)}"
        )

    async def create_published(self, user_email: str, source: Canvas) -> Canvas:
        """Create the canvas row for a published snapshot. Views are copied
        by `ViewsService.copy_for_publish` so that storage logic stays in one
        place (matters for the fake/test implementation).
        """
        if source.status == "published":
            raise AppError(
                FORBIDDEN,
                "Already published — re-publish the source draft instead.",
                status_code=403,
            )
        published = Canvas(
            id=uuid.uuid4().hex,
            user_email=user_email,
            name=source.name,
            status="published",
            source_canvas_id=source.id,
        )
        await self._insert(published)
        return published

    async def ensure_default(self, user_email: str) -> Canvas:
        """Return the user's most-recent draft canvas, creating one if absent.

        Used as the legacy backfill target and as the default destination for
        a pin that doesn't specify a canvas_id.
        """
        canvases = await self.list(user_email)
        for c in canvases:
            if c.status == "draft":
                return c
        return await self.create(user_email, DEFAULT_CANVAS_NAME)
