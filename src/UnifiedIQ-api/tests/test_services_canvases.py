"""Unit-level tests for CanvasService + new ViewsService paths.

Uses an in-process StubWarehouse that mimics enough Delta SQL semantics
(INSERT / SELECT / UPDATE / DELETE on a single table) for the service
methods to round-trip rows. The real DatabricksWarehouse is covered by
integration tests run against the deployed app.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from app.config import Settings
from app.errors import AppError
from app.models.domain import ViewSpec
from app.services.canvases import CanvasService
from app.services.views import ViewsService


class StubWarehouse:
    """Minimal SQL emulator for `user_canvases` + `user_views` tables."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}

    async def execute(self, sql: str, *, params: Any = None) -> list[dict]:
        s = sql.strip()
        head = s.split(None, 1)[0].upper()

        if head == "CREATE":
            m = re.search(r"CREATE TABLE IF NOT EXISTS\s+([\w.]+)\s*\(", s, re.I)
            if m:
                self.tables.setdefault(m.group(1), [])
            return []

        if head == "INSERT":
            m = re.search(r"INSERT INTO\s+([\w.]+)\s+VALUES\s*\((.*)\)\s*$", s, re.I | re.S)
            assert m, f"unparseable insert: {s}"
            table = m.group(1)
            values = self._split_values(m.group(2))
            if table.endswith("user_canvases"):
                self.tables.setdefault(table, []).append(
                    {
                        "canvas_id": values[0],
                        "user_email": values[1],
                        "name": values[2],
                        "status": values[3],
                        "source_canvas_id": values[4],
                        "created_at": values[5],
                        "updated_at": values[6],
                    }
                )
            elif table.endswith("user_views"):
                self.tables.setdefault(table, []).append(
                    {
                        "view_id": values[0],
                        "user_email": values[1],
                        "name": values[2],
                        "kind": values[3],
                        "spec": values[4],
                        "is_shared": values[5] == "true",
                        "created_at": values[6],
                        "updated_at": values[7],
                    }
                )
            return []

        if head == "SELECT":
            m = re.search(r"FROM\s+([\w.]+)", s, re.I)
            assert m, f"unparseable select: {s}"
            rows = list(self.tables.get(m.group(1), []))
            where = re.search(r"WHERE\s+(.+?)(?:ORDER BY|$)", s, re.I | re.S)
            if where:
                rows = [r for r in rows if self._match_where(r, where.group(1))]
            return rows

        if head == "DELETE":
            m = re.search(r"DELETE FROM\s+([\w.]+)\s+WHERE\s+(.+)$", s, re.I | re.S)
            assert m, f"unparseable delete: {s}"
            table = m.group(1)
            before = self.tables.get(table, [])
            self.tables[table] = [r for r in before if not self._match_where(r, m.group(2))]
            return []

        if head == "UPDATE":
            m = re.search(
                r"UPDATE\s+([\w.]+)\s+SET\s+(.+?)\s+WHERE\s+(.+)$",
                s,
                re.I | re.S,
            )
            assert m, f"unparseable update: {s}"
            table = m.group(1)
            assigns = self._parse_assigns(m.group(2))
            for r in self.tables.get(table, []):
                if self._match_where(r, m.group(3)):
                    for col, val in assigns.items():
                        r[col] = val
            return []

        raise AssertionError(f"unhandled SQL: {s}")

    @staticmethod
    def _split_values(payload: str) -> list[str]:
        out: list[str] = []
        depth = 0
        cur = ""
        in_str = False
        i = 0
        while i < len(payload):
            ch = payload[i]
            if ch == "'" and (i == 0 or payload[i - 1] != "\\"):
                in_str = not in_str
                cur += ch
            elif ch == "(" and not in_str:
                depth += 1
                cur += ch
            elif ch == ")" and not in_str:
                depth -= 1
                cur += ch
            elif ch == "," and not in_str and depth == 0:
                out.append(StubWarehouse._unquote(cur.strip()))
                cur = ""
            else:
                cur += ch
            i += 1
        if cur.strip():
            out.append(StubWarehouse._unquote(cur.strip()))
        return out

    @staticmethod
    def _unquote(token: str) -> Any:
        if token == "NULL":
            return None
        if token.startswith("TIMESTAMP '") and token.endswith("'"):
            return token[len("TIMESTAMP '") : -1]
        if token.startswith("'") and token.endswith("'"):
            inner = token[1:-1].replace("''", "'")
            return inner
        if token.lower() in ("true", "false"):
            return token.lower()
        return token

    @staticmethod
    def _parse_assigns(payload: str) -> dict[str, Any]:
        # `col = <literal>, col = <literal>, ...`
        out: dict[str, Any] = {}
        for chunk in re.split(r",\s*(?=\w+\s*=)", payload):
            m = re.match(r"(\w+)\s*=\s*(.+)", chunk.strip(), re.S)
            assert m, f"bad assign: {chunk}"
            out[m.group(1)] = StubWarehouse._unquote(m.group(2).strip())
        return out

    @staticmethod
    def _match_where(row: dict, clause: str) -> bool:
        # AND-only equality predicates (`col = '...'`).
        for cond in re.split(r"\s+AND\s+", clause, flags=re.I):
            m = re.match(r"(\w+)\s*=\s*(.+)", cond.strip(), re.S)
            assert m, f"unsupported where: {cond}"
            col, lit = m.group(1), StubWarehouse._unquote(m.group(2).strip())
            if row.get(col) != lit:
                return False
        return True


def _settings() -> Settings:
    return Settings(warehouse_catalog="workspace", warehouse_schema="default")


@pytest.fixture
def services() -> tuple[CanvasService, ViewsService, StubWarehouse]:
    wh = StubWarehouse()
    settings = _settings()
    canvases = CanvasService(settings, wh)  # type: ignore[arg-type]
    views = ViewsService(settings, wh, canvases)  # type: ignore[arg-type]
    return canvases, views, wh


async def test_canvas_crud_roundtrip(services):
    canvases, _views, _wh = services
    await canvases.ensure_table()
    c = await canvases.create("u@x.com", "First")
    assert c.status == "draft"

    fetched = await canvases.get("u@x.com", c.id)
    assert fetched is not None and fetched.name == "First"

    renamed = await canvases.rename("u@x.com", c.id, "First v2")
    assert renamed is not None and renamed.name == "First v2"

    # Listing returns the row
    listed = await canvases.list("u@x.com")
    assert len(listed) == 1 and listed[0].id == c.id

    await canvases.delete("u@x.com", c.id)
    assert await canvases.get("u@x.com", c.id) is None


async def test_publish_creates_published_snapshot(services):
    canvases, views, _wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    draft = await canvases.create("u@x.com", "Ops")
    spec = ViewSpec(
        question="q",
        sql="SELECT 1 AS v",
        canvas_id=draft.id,
    )
    src = await views.create("u@x.com", "kpi", spec)

    published = await canvases.create_published("u@x.com", draft)
    assert published.status == "published"
    assert published.source_canvas_id == draft.id

    copies = await views.copy_for_publish("u@x.com", published.id, [src])
    assert len(copies) == 1
    assert copies[0].id != src.id
    assert copies[0].spec.canvas_id == published.id

    # Re-publishing a published canvas is blocked
    with pytest.raises(AppError) as exc:
        await canvases.create_published("u@x.com", published)
    assert exc.value.status_code == 403


async def test_views_blocked_when_canvas_published(services):
    canvases, views, _wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    draft = await canvases.create("u@x.com", "Draft")
    src = await views.create(
        "u@x.com",
        "v",
        ViewSpec(question="q", sql="SELECT 1 AS v", canvas_id=draft.id),
    )
    published = await canvases.create_published("u@x.com", draft)
    copies = await views.copy_for_publish("u@x.com", published.id, [src])
    pub_view = copies[0]

    with pytest.raises(AppError) as exc:
        await views.update("u@x.com", pub_view.id, name="changed")
    assert exc.value.status_code == 403

    with pytest.raises(AppError):
        await views.delete("u@x.com", pub_view.id)

    with pytest.raises(AppError):
        await canvases.rename("u@x.com", published.id, "nope")
    with pytest.raises(AppError):
        await canvases.delete("u@x.com", published.id)


async def test_create_view_without_canvas_routes_to_default(services):
    canvases, views, _wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    spec = ViewSpec(question="q", sql="SELECT 1 AS v")
    created = await views.create("u@x.com", "orphan", spec)
    assert created.spec.canvas_id is not None
    default = await canvases.get("u@x.com", created.spec.canvas_id)
    assert default is not None and default.status == "draft"


async def test_run_view_rejects_non_select(services):
    canvases, views, wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    draft = await canvases.create("u@x.com", "C")
    # Bypass the service-level INSERT path; inject a malicious spec directly.
    bad_view_id = "evil"
    spec = ViewSpec(question="q", sql="DROP TABLE x", canvas_id=draft.id)
    wh.tables.setdefault("workspace.default.user_views", []).append(
        {
            "view_id": bad_view_id,
            "user_email": "u@x.com",
            "name": "n",
            "kind": "chart",
            "spec": json.dumps(spec.model_dump()),
            "is_shared": False,
            "created_at": "2026-05-19 00:00:00",
            "updated_at": "2026-05-19 00:00:00",
        }
    )
    with pytest.raises(AppError) as exc:
        await views.run("u@x.com", bad_view_id)
    assert exc.value.status_code == 422


async def test_cascade_delete_in_canvas(services):
    canvases, views, _wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    c1 = await canvases.create("u@x.com", "A")
    c2 = await canvases.create("u@x.com", "B")
    await views.create("u@x.com", "a", ViewSpec(question="q", sql="SELECT 1 AS v", canvas_id=c1.id))
    await views.create("u@x.com", "b", ViewSpec(question="q", sql="SELECT 1 AS v", canvas_id=c2.id))
    assert len(await views.list("u@x.com")) == 2
    await views.delete_in_canvas("u@x.com", c1.id)
    remaining = await views.list("u@x.com")
    assert len(remaining) == 1 and remaining[0].spec.canvas_id == c2.id


async def test_backfill_assigns_orphan_views(services):
    canvases, views, wh = services
    await canvases.ensure_table()
    await views.ensure_table()
    # Pre-seed two orphan rows (no canvas_id in spec) for the same user.
    wh.tables.setdefault("workspace.default.user_views", []).extend(
        [
            {
                "view_id": f"orphan-{i}",
                "user_email": "u@x.com",
                "name": f"n{i}",
                "kind": "chart",
                "spec": json.dumps(
                    {
                        "question": "q",
                        "sql": "SELECT 1 AS v",
                        "default_view": "table",
                    }
                ),
                "is_shared": False,
                "created_at": "2026-05-19 00:00:00",
                "updated_at": "2026-05-19 00:00:00",
            }
            for i in range(2)
        ]
    )

    await views.backfill_canvas_ids()

    rows = wh.tables["workspace.default.user_views"]
    cids = {json.loads(r["spec"]).get("canvas_id") for r in rows}
    # Both orphans now share a single default canvas id.
    assert None not in cids
    assert len(cids) == 1
    cid = next(iter(cids))
    canvas = await canvases.get("u@x.com", cid)
    assert canvas is not None and canvas.status == "draft"
