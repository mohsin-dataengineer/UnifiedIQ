"""SchemaService - Tier 1 of the memory strategy.

Fetches table/column metadata from each configured `<catalog>.<schema>`
via `information_schema`, caches the result, and exposes a keyword-filtered
view that the chat router injects into the planner prompt so the model
stops inventing table names.
"""

from __future__ import annotations

import logging
import re

from app.config import Settings
from app.models.domain import ColumnInfo, TableInfo
from app.services.cache import CacheService
from app.services.warehouse import WarehouseService

logger = logging.getLogger(__name__)

_CACHE_KEY = "schema:all"
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


class SchemaService:
    def __init__(self, settings: Settings, warehouse: WarehouseService) -> None:
        self._settings = settings
        self._wh = warehouse
        # Dedicated long-TTL cache so schema fetches don't fight for slots
        # with chat-time caches.
        self._cache = CacheService(maxsize=16, ttl=settings.schema_ttl_seconds)

    async def _fetch_source(self, catalog: str, schema: str) -> list[TableInfo]:
        """One source = one (catalog, schema)."""
        sql = (
            f"SELECT table_name, column_name, data_type, comment "
            f"FROM {catalog}.information_schema.columns "
            f"WHERE table_schema = '{schema}' "
            f"ORDER BY table_name, ordinal_position"
        )
        rows = await self._wh.execute(sql)
        by_table: dict[str, TableInfo] = {}
        for r in rows:
            tname = r["table_name"]
            t = by_table.get(tname)
            if t is None:
                t = TableInfo(catalog=catalog, schema=schema, table=tname, columns=[])
                by_table[tname] = t
            t.columns.append(
                ColumnInfo(
                    name=r["column_name"],
                    data_type=str(r.get("data_type") or ""),
                    comment=r.get("comment"),
                )
            )
        return list(by_table.values())

    async def all_tables(self) -> list[TableInfo]:
        cached = self._cache.get(_CACHE_KEY)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        out: list[TableInfo] = []
        for catalog, schema in self._settings.schema_source_list:
            try:
                out.extend(await self._fetch_source(catalog, schema))
            except Exception:  # noqa: BLE001 - one bad source must not kill all
                logger.exception("schema fetch failed for %s.%s", catalog, schema)
        self._cache.set(_CACHE_KEY, out)
        return out

    def relevant_tables(
        self, tables: list[TableInfo], question: str, *, top_k: int
    ) -> list[TableInfo]:
        """Rank tables by keyword overlap with the question. Falls back to
        the first `top_k` tables when no overlap (so we always inject
        *something* on a brand-new chat)."""
        words = {w.lower() for w in _WORD.findall(question) if len(w) >= 3}
        if not words:
            return tables[:top_k]
        scored: list[tuple[int, TableInfo]] = []
        for t in tables:
            haystack = " ".join(
                [t.table, t.catalog, t.schema_, t.comment or ""]
                + [c.name for c in t.columns]
                + [c.comment or "" for c in t.columns]
            ).lower()
            score = sum(1 for w in words if w in haystack)
            scored.append((score, t))
        scored.sort(key=lambda x: (-x[0], x[1].qualified))
        # Keep some baseline even when nothing matched, so the prompt
        # still has a useful catalogue.
        chosen = [t for s, t in scored if s > 0][:top_k]
        if not chosen:
            chosen = [t for _, t in scored][:top_k]
        return chosen

    async def context_block(self, question: str) -> str:
        """Return a compact text block to append to the planner system prompt."""
        tables = await self.all_tables()
        if not tables:
            return ""
        picked = self.relevant_tables(
            tables, question, top_k=self._settings.schema_max_tables_injected
        )
        if not picked:
            return ""
        lines: list[str] = []
        for t in picked:
            cols = ", ".join(f"{c.name} {c.data_type}".strip() for c in t.columns)
            note = f"  -- {t.comment}" if t.comment else ""
            lines.append(f"{t.qualified}({cols}){note}")
        return "## Available tables\n" + "\n".join(lines)
