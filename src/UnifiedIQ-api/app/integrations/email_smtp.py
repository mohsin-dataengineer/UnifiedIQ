"""Email integration over SMTP (stdlib smtplib, run off the event loop).

Service-scoped. Supported action: `send` with params {to, subject, body}.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import Settings
from app.errors import INTEGRATION_ERROR, AppError
from app.integrations.base import BaseIntegration
from app.models.domain import AuthContext, HealthStatus

logger = logging.getLogger(__name__)


class EmailIntegration(BaseIntegration):
    name = "email"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self, user_token: str | None) -> AuthContext:
        if not self._settings.smtp_host:
            raise AppError(INTEGRATION_ERROR, "SMTP is not configured", status_code=503)
        return AuthContext(principal="smtp", metadata={"integration": self.name})

    def _send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(
            self._settings.smtp_host,
            self._settings.smtp_port,
            timeout=self._settings.smtp_timeout_seconds,
        ) as srv:
            if self._settings.smtp_use_tls:
                srv.starttls()
            if self._settings.smtp_username:
                srv.login(
                    self._settings.smtp_username,
                    self._settings.smtp_password,
                )
            srv.send_message(msg)

    async def execute(self, action: str, params: dict[str, Any], *, ctx: AuthContext) -> Any:
        if action != "send":
            raise AppError(
                INTEGRATION_ERROR,
                f"Unsupported email action: {action}",
                status_code=400,
            )
        try:
            await asyncio.to_thread(
                self._send,
                params["to"],
                params.get("subject", "(no subject)"),
                params["body"],
            )
        except Exception as exc:  # noqa: BLE001 - normalized to stable code
            logger.exception("smtp send failed")
            raise AppError(INTEGRATION_ERROR, "Email send failed", status_code=502) from exc
        return {"delivered_to": params["to"]}

    async def health(self) -> HealthStatus:
        if not self._settings.smtp_host:
            return HealthStatus(name=self.name, healthy=False, detail="not configured")

        def _probe() -> None:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=self._settings.smtp_timeout_seconds,
            ) as srv:
                srv.noop()

        try:
            await asyncio.to_thread(_probe)
            return HealthStatus(name=self.name, healthy=True)
        except Exception as exc:  # noqa: BLE001 - health is best-effort
            return HealthStatus(name=self.name, healthy=False, detail=str(exc))
