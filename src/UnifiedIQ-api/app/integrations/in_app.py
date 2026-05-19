"""In-app notification channel. Lets alerts be observed with zero external
config. Per-user in-memory ring buffer (newest first)."""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from app.config import Settings
from app.integrations.base import BaseIntegration
from app.models.domain import AuthContext, HealthStatus, Notification


class InAppIntegration(BaseIntegration):
    name = "in_app"

    def __init__(self, settings: Settings) -> None:
        self._max = settings.alerts_in_app_max
        self._feeds: dict[str, deque[Notification]] = {}

    async def authenticate(self, user_token: str | None) -> AuthContext:
        return AuthContext(principal="in-app")

    async def execute(self, action: str, params: dict[str, Any], *, ctx: AuthContext) -> Any:
        if action != "notify":
            return {"ok": False}
        n = Notification(
            id=uuid.uuid4().hex,
            user_email=params["user_email"],
            title=params["title"],
            message=params["message"],
        )
        feed = self._feeds.setdefault(n.user_email, deque(maxlen=self._max))
        feed.appendleft(n)
        return {"ok": True, "id": n.id}

    async def health(self) -> HealthStatus:
        return HealthStatus(name=self.name, healthy=True)

    def recent(self, user_email: str) -> list[Notification]:
        return list(self._feeds.get(user_email, []))
