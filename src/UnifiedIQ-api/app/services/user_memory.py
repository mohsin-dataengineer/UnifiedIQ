"""UserMemoryService - Tier 4 of the memory strategy.

Persistent per-user facts/preferences. Same warehouse-backed shape as
alerts and views; carries `user_email` on every row (Principle 7).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.config import Settings
from app.models.domain import UserMemory
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


class UserMemoryService:
    def __init__(self, settings: Settings, warehouse: WarehouseService) -> None:
        self._settings = settings
        self._wh = warehouse
        self._table = settings.user_memory_table_name

    async def ensure_table(self) -> None:
        await self._wh.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table} ("
            "id STRING, user_email STRING, value STRING, "
            "created_at TIMESTAMP, updated_at TIMESTAMP) USING DELTA"
        )

    def _row(self, r: dict) -> UserMemory:
        return UserMemory(
            id=r["id"],
            user_email=r["user_email"],
            value=r["value"],
            created_at=r.get("created_at") or _now(),
            updated_at=r.get("updated_at") or _now(),
        )

    async def create(self, user_email: str, value: str) -> UserMemory:
        now = _now()
        m = UserMemory(
            id=uuid.uuid4().hex,
            user_email=user_email,
            value=value.strip(),
            created_at=now,
            updated_at=now,
        )
        await self._wh.execute(
            f"INSERT INTO {self._table} VALUES ("
            f"{_q(m.id)}, {_q(m.user_email)}, {_q(m.value)}, "
            f"{_ts(m.created_at)}, {_ts(m.updated_at)})"
        )
        return m

    async def list(self, user_email: str) -> list[UserMemory]:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE user_email = {_q(user_email)} "
            "ORDER BY created_at ASC"
        )
        return [self._row(r) for r in rows]

    async def delete(self, user_email: str, memory_id: str) -> None:
        await self._wh.execute(
            f"DELETE FROM {self._table} WHERE id = {_q(memory_id)} "
            f"AND user_email = {_q(user_email)}"
        )

    async def context_block(self, user_email: str) -> str:
        """Return a compact markdown block to prepend to the planner prompt."""
        try:
            items = await self.list(user_email)
        except Exception:  # noqa: BLE001 - chat must work without memory
            logger.exception("user_memory list failed")
            return ""
        if not items:
            return ""
        bullets = "\n".join(f"- {m.value}" for m in items)
        return "## User context (remember about this user)\n" + bullets
