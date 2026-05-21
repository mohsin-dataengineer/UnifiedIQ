"""Core domain Pydantic types shared across services and routers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ChartType = Literal["line", "bar", "pie", "area", "scatter", "table", "none"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ChartConfig(BaseModel):
    """Recharts-friendly chart spec. `none` means render as a table."""

    type: ChartType = "none"
    title: str | None = None
    x: str | None = None
    y: list[str] = Field(default_factory=list)
    series: str | None = None
    stacked: bool = False


class Citation(BaseModel):
    id: str
    title: str
    url: str | None = None


class CurrentUser(BaseModel):
    """The authenticated end user, derived from a validated OIDC bearer."""

    email: str
    name: str | None = None
    groups: list[str] = Field(default_factory=list)


class AuthContext(BaseModel):
    """Auth context handed to an integration's `execute`."""

    principal: str
    token: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    name: str
    healthy: bool
    detail: str | None = None


class SessionTurn(BaseModel):
    session_id: str
    user_email: str
    role: Literal["user", "assistant"]
    content: str
    interaction_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class TelemetryEvent(BaseModel):
    event_type: str
    user_email: str
    request_id: str
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class Alert(BaseModel):
    """A persisted natural-language monitor (carries user_email, Principle 7)."""

    id: str
    user_email: str
    title: str
    natural_language: str
    metric_sql: str
    comparator: Literal["lt", "lte", "gt", "gte", "eq", "neq"]
    threshold: float
    channel: Literal["in_app", "slack", "email"]
    recipient: str | None = None
    cadence_minutes: int = 60
    enabled: bool = True
    last_state: Literal["pending", "ok", "breached", "error"] = "pending"
    last_value: float | None = None
    last_checked_at: datetime | None = None
    # Set => one-shot scheduled alert; fires once at/after this UTC time and
    # then auto-disables. Null => recurring on cadence_minutes.
    scheduled_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Notification(BaseModel):
    id: str
    user_email: str
    title: str
    message: str
    alert_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ColumnInfo(BaseModel):
    name: str
    data_type: str = ""
    comment: str | None = None


class TableInfo(BaseModel):
    """One warehouse table as exposed to the planner prompt."""

    catalog: str
    schema_: str = Field(alias="schema")
    table: str
    comment: str | None = None
    columns: list[ColumnInfo] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @property
    def qualified(self) -> str:
        return f"{self.catalog}.{self.schema_}.{self.table}"


class UserMemory(BaseModel):
    """A persisted user-supplied fact / preference (Principle 7)."""

    id: str
    user_email: str
    value: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class VerificationResult(BaseModel):
    """Self-audit result: re-derives a metric a different way + LLM judge."""

    verdict: Literal["agree", "disagree", "inconclusive"]
    confidence: float = Field(ge=0.0, le=1.0)
    original_value: float | None = None
    alternative_value: float | None = None
    alternative_sql: str
    alternative_approach: str
    rationale: str
    diff_pct: float | None = None


class ViewSpec(BaseModel):
    """Saved chart/KPI spec for a pinned dashboard view."""

    question: str
    sql: str
    chart_config: ChartConfig | None = None
    default_view: Literal["bar", "line", "area", "pie", "table", "kpi"] = "table"
    # Customization (all optional; UI-controlled).
    filter_text: str | None = None
    layout: dict[str, int] | None = None  # {w: 1|2, h: 1|2, position: int}
    colors: list[str] | None = None
    x_label: str | None = None
    y_label: str | None = None
    # The canvas this view belongs to. Required after the 2026-05 migration;
    # legacy rows are backfilled to a per-user "My canvas" on first load.
    canvas_id: str | None = None


class UserView(BaseModel):
    """A pinned dashboard view (Principle 7: user_email per row)."""

    id: str
    user_email: str
    name: str
    kind: Literal["chart", "table", "dashboard"] = "chart"
    spec: ViewSpec
    is_shared: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


CanvasStatus = Literal["draft", "published"]


class Canvas(BaseModel):
    """A grouping of pinned views.

    `status=draft` canvases are mutable. `status=published` canvases (and the
    views they contain) are immutable snapshots created via `publish`.
    """

    id: str
    user_email: str
    name: str
    status: CanvasStatus = "draft"
    # When status=published, points back to the draft this was copied from.
    source_canvas_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
