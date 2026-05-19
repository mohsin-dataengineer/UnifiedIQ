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
    created_at: datetime = Field(default_factory=_utcnow)


class Notification(BaseModel):
    id: str
    user_email: str
    title: str
    message: str
    created_at: datetime = Field(default_factory=_utcnow)
