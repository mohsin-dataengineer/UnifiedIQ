"""Slack integration. Reference implementation of BaseIntegration.

Service-scoped: authenticates with the configured bot token (not the end
user's token). Supported action: `post_message`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.errors import INTEGRATION_ERROR, AppError
from app.integrations.base import BaseIntegration
from app.models.domain import AuthContext, HealthStatus

logger = logging.getLogger(__name__)


class SlackIntegration(BaseIntegration):
    name = "slack"

    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def authenticate(self, user_token: str | None) -> AuthContext:
        if not self._settings.slack_bot_token:
            raise AppError(INTEGRATION_ERROR, "Slack is not configured", status_code=503)
        return AuthContext(
            principal="slack-bot",
            token=self._settings.slack_bot_token,
            metadata={"integration": self.name},
        )

    async def execute(self, action: str, params: dict[str, Any], *, ctx: AuthContext) -> Any:
        if action != "post_message":
            raise AppError(
                INTEGRATION_ERROR,
                f"Unsupported Slack action: {action}",
                status_code=400,
            )
        payload = {
            "channel": params.get("channel") or self._settings.slack_default_channel,
            "text": params["text"],
        }
        resp = await self._http.post(
            f"{self._settings.slack_api_base}/chat.postMessage",
            headers={"Authorization": f"Bearer {ctx.token}"},
            json=payload,
        )
        body = resp.json()
        if not body.get("ok"):
            raise AppError(
                INTEGRATION_ERROR,
                f"Slack error: {body.get('error', 'unknown')}",
                status_code=502,
            )
        return {"ts": body.get("ts"), "channel": body.get("channel")}

    async def health(self) -> HealthStatus:
        if not self._settings.slack_bot_token:
            return HealthStatus(name=self.name, healthy=False, detail="not configured")
        try:
            resp = await self._http.post(
                f"{self._settings.slack_api_base}/auth.test",
                headers={"Authorization": f"Bearer {self._settings.slack_bot_token}"},
            )
            ok = bool(resp.json().get("ok"))
            return HealthStatus(
                name=self.name,
                healthy=ok,
                detail=None if ok else "auth.test failed",
            )
        except Exception as exc:  # noqa: BLE001 - health is best-effort
            return HealthStatus(name=self.name, healthy=False, detail=str(exc))
