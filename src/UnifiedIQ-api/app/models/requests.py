"""Inbound request bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class IntegrationExecuteRequest(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)


class CreateViewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    question: str = Field(min_length=1, max_length=2000)
    sql: str = Field(min_length=1, max_length=10000)
    chart_config: dict | None = None
    default_view: Literal["bar", "line", "area", "pie", "table", "kpi"] = "table"
    # Optional during the transition: if omitted, ViewsService routes the new
    # pin to the user's default draft canvas (creating it if needed).
    canvas_id: str | None = None


class UpdateViewRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    # Partial spec patch (any subset of ViewSpec fields). Merged server-side.
    spec: dict | None = None


class CreateCanvasRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)


class UpdateCanvasRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)


class VerifyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    original_sql: str = Field(min_length=1, max_length=10000)


class CreateAlertRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # User-controlled overrides. The LLM still derives metric_sql + comparator
    # + threshold; these win over whatever the model picks for delivery.
    cadence_minutes: int | None = Field(default=None, ge=5, le=10080)
    channel: Literal["email", "slack"] | None = None
    recipient: str | None = Field(default=None, max_length=320)
    # ISO datetime; when set the alert is one-shot and fires at/after this time.
    scheduled_at: datetime | None = None


class CreateMemoryRequest(BaseModel):
    value: str = Field(min_length=1, max_length=500)
