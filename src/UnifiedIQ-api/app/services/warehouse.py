"""WarehouseService - the text-to-SQL execution surface.

`WarehouseService` is the structural contract (Part 2.4). `DatabricksWarehouse`
is the only concrete implementation; the databricks-sql-connector is blocking,
so calls run in a worker thread and are bounded by a query timeout.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

import pyarrow as pa

from app.config import Settings
from app.errors import WAREHOUSE_ERROR, WAREHOUSE_TIMEOUT, AppError

logger = logging.getLogger(__name__)


class WarehouseService(Protocol):
    async def execute(
        self, sql: str, *, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...

    async def execute_to_arrow(self, sql: str) -> pa.Table: ...

    async def health(self) -> bool: ...


class DatabricksWarehouse:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _connect(self):  # noqa: ANN202 - third-party connection object
        from databricks import sql

        return sql.connect(
            server_hostname=self._settings.warehouse_server_hostname,
            http_path=self._settings.warehouse_http_path,
            access_token=self._settings.warehouse_access_token,
            catalog=self._settings.warehouse_catalog,
            schema=self._settings.warehouse_schema,
        )

    def _run_dicts(self, sql: str, params: dict[str, Any] | None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def _run_arrow(self, sql: str) -> pa.Table:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall_arrow()

    async def execute(
        self, sql: str, *, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self._guarded(asyncio.to_thread(self._run_dicts, sql, params))

    async def execute_to_arrow(self, sql: str) -> pa.Table:
        return await self._guarded(asyncio.to_thread(self._run_arrow, sql))

    async def health(self) -> bool:
        try:
            await self.execute("SELECT 1")
            return True
        except AppError:
            return False

    async def _guarded(self, coro):  # noqa: ANN001, ANN202
        try:
            return await asyncio.wait_for(
                coro, timeout=self._settings.warehouse_query_timeout_seconds
            )
        except TimeoutError as exc:
            raise AppError(WAREHOUSE_TIMEOUT, "Warehouse query timed out", status_code=504) from exc
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalized to a stable code
            logger.exception("warehouse query failed")
            raise AppError(WAREHOUSE_ERROR, "Warehouse query failed", status_code=502) from exc
