"""Inbound request bodies."""

from __future__ import annotations

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


class CreateAlertRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
