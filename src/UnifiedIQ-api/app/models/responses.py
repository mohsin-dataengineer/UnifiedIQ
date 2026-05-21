"""Response models. LLM-driven logic must route on a structured model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.domain import ChartConfig, Citation


class SQLGenerationResponse(BaseModel):
    """Structured output for the text-to-SQL planning step (Part 2.6)."""

    intent: Literal["data", "chart", "reject", "clarify"]
    sql: str | None = None
    chart_config: ChartConfig | None = None
    assumptions: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None
    rejection_reason: str | None = None


class AlternativeSQLResponse(BaseModel):
    """LLM picks an independent SQL approach to compute the same metric."""

    alternative_sql: str | None = None
    approach: str = ""
    reject_reason: str | None = None


class JudgeScore(BaseModel):
    """LLM-as-judge verdict over two result snapshots for the same question."""

    verdict: Literal["agree", "disagree", "inconclusive"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


Comparator = Literal["lt", "lte", "gt", "gte", "eq", "neq"]
AlertChannel = Literal["in_app", "slack", "email"]


class AlertSpec(BaseModel):
    """Structured output: a natural-language alert compiled to a monitor."""

    title: str
    metric_sql: str | None = None
    comparator: Comparator | None = None
    threshold: float | None = None
    channel: AlertChannel = "in_app"
    recipient: str | None = None
    cadence_minutes: int = 60
    scheduled_at: datetime | None = None
    reject_reason: str | None = None


class ChatResponse(BaseModel):
    interaction_id: str
    session_id: str
    intent: str
    answer: str | None = None
    sql: str | None = None
    chart_config: ChartConfig | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    git_sha: str
    dependencies: dict[str, bool] = Field(default_factory=dict)
