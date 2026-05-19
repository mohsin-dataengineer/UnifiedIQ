"""AlertService - persists natural-language monitors in the warehouse,
evaluates due ones, and fires through the integration registry.

Storage uses the warehouse (user choice). SQL is built with strict value
quoting; enum/numeric fields are validated, free text is escaped.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.models.domain import Alert
from app.models.responses import AlertSpec
from app.services.integration_registry import IntegrationRegistry
from app.services.warehouse import WarehouseService

logger = logging.getLogger(__name__)

_OPS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
}
_SYM = {
    "lt": "<",
    "lte": "≤",
    "gt": ">",
    "gte": "≥",
    "eq": "=",
    "neq": "≠",
}


def breached(value: float, comparator: str, threshold: float) -> bool:
    return _OPS[comparator](value, threshold)


def _q(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _ts(dt: datetime | None) -> str:
    if dt is None:
        return "NULL"
    return f"TIMESTAMP '{dt.astimezone(UTC):%Y-%m-%d %H:%M:%S}'"


def _now() -> datetime:
    return datetime.now(UTC)


class AlertService:
    def __init__(
        self,
        settings: Settings,
        warehouse: WarehouseService,
        registry: IntegrationRegistry,
    ) -> None:
        self._settings = settings
        self._wh = warehouse
        self._registry = registry
        self._table = settings.alerts_table_name

    async def ensure_table(self) -> None:
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {self._table} ("
            "id STRING, user_email STRING, title STRING, "
            "natural_language STRING, metric_sql STRING, comparator STRING, "
            "threshold DOUBLE, channel STRING, recipient STRING, "
            "cadence_minutes INT, enabled BOOLEAN, last_state STRING, "
            "last_value DOUBLE, last_checked_at TIMESTAMP, "
            "created_at TIMESTAMP) USING DELTA"
        )
        await self._wh.execute(ddl)

    def _row_to_alert(self, r: dict) -> Alert:
        return Alert(
            id=r["id"],
            user_email=r["user_email"],
            title=r["title"],
            natural_language=r["natural_language"],
            metric_sql=r["metric_sql"],
            comparator=r["comparator"],
            threshold=float(r["threshold"]),
            channel=r["channel"],
            recipient=r.get("recipient"),
            cadence_minutes=int(r["cadence_minutes"]),
            enabled=bool(r["enabled"]),
            last_state=r.get("last_state") or "pending",
            last_value=(float(r["last_value"]) if r.get("last_value") is not None else None),
            last_checked_at=r.get("last_checked_at"),
            created_at=r.get("created_at") or _now(),
        )

    async def create(self, user_email: str, natural_language: str, spec: AlertSpec) -> Alert:
        alert = Alert(
            id=uuid.uuid4().hex,
            user_email=user_email,
            title=spec.title,
            natural_language=natural_language,
            metric_sql=spec.metric_sql or "",
            comparator=spec.comparator or "lt",
            threshold=float(spec.threshold or 0),
            channel=spec.channel,
            recipient=spec.recipient,
            cadence_minutes=max(5, int(spec.cadence_minutes or 60)),
        )
        await self._wh.execute(
            f"INSERT INTO {self._table} VALUES ("
            f"{_q(alert.id)}, {_q(alert.user_email)}, {_q(alert.title)}, "
            f"{_q(alert.natural_language)}, {_q(alert.metric_sql)}, "
            f"{_q(alert.comparator)}, {alert.threshold}, "
            f"{_q(alert.channel)}, {_q(alert.recipient)}, "
            f"{alert.cadence_minutes}, {str(alert.enabled).lower()}, "
            f"{_q(alert.last_state)}, NULL, NULL, {_ts(alert.created_at)})"
        )
        return alert

    async def list(self, user_email: str) -> list[Alert]:
        rows = await self._wh.execute(
            f"SELECT * FROM {self._table} WHERE user_email = {_q(user_email)} "
            "ORDER BY created_at DESC"
        )
        return [self._row_to_alert(r) for r in rows]

    async def delete(self, user_email: str, alert_id: str) -> None:
        await self._wh.execute(
            f"DELETE FROM {self._table} WHERE id = {_q(alert_id)} AND user_email = {_q(user_email)}"
        )

    async def _evaluate(self, alert: Alert) -> tuple[float | None, str | None]:
        try:
            rows = await self._wh.execute(alert.metric_sql)
        except Exception as exc:  # noqa: BLE001 - recorded as error state
            return None, str(exc)[:200]
        if not rows:
            return None, "metric query returned no rows"
        first = next(iter(rows[0].values()))
        try:
            return float(first), None
        except (TypeError, ValueError):
            return None, "metric is not numeric"

    async def _persist_state(self, alert: Alert, state: str, value: float | None) -> None:
        val = "NULL" if value is None else str(value)
        await self._wh.execute(
            f"UPDATE {self._table} SET last_state = {_q(state)}, "
            f"last_value = {val}, last_checked_at = {_ts(_now())} "
            f"WHERE id = {_q(alert.id)}"
        )

    async def _fire(self, alert: Alert, value: float) -> None:
        msg = (
            f"Alert '{alert.title}': metric is {value:g} "
            f"({_SYM[alert.comparator]} {alert.threshold:g})."
        )
        # Always surface in-app so it's observable without external config.
        try:
            in_app = self._registry.get("in_app")
            await in_app.execute(
                "notify",
                {
                    "user_email": alert.user_email,
                    "title": alert.title,
                    "message": msg,
                },
                ctx=await in_app.authenticate(None),
            )
        except Exception:  # noqa: BLE001 - delivery best-effort
            logger.exception("in_app notify failed")

        if alert.channel in ("slack", "email"):
            try:
                integ = self._registry.get(alert.channel)
                ctx = await integ.authenticate(None)
                if alert.channel == "slack":
                    await integ.execute(
                        "post_message",
                        {"channel": alert.recipient, "text": msg},
                        ctx=ctx,
                    )
                else:
                    await integ.execute(
                        "send",
                        {
                            "to": alert.recipient,
                            "subject": f"UnifiedIQ alert: {alert.title}",
                            "body": msg,
                        },
                        ctx=ctx,
                    )
            except Exception:  # noqa: BLE001 - channel may be unconfigured
                logger.exception("alert %s channel delivery failed", alert.id)

    async def evaluate_one(self, alert: Alert) -> Alert:
        value, err = await self._evaluate(alert)
        if err is not None or value is None:
            await self._persist_state(alert, "error", None)
            alert.last_state = "error"
            return alert
        is_breach = breached(value, alert.comparator, alert.threshold)
        if is_breach and alert.last_state != "breached":
            await self._fire(alert, value)
        new_state = "breached" if is_breach else "ok"
        await self._persist_state(alert, new_state, value)
        alert.last_state = new_state
        alert.last_value = value
        return alert

    async def run_now(self, user_email: str, alert_id: str) -> Alert | None:
        for a in await self.list(user_email):
            if a.id == alert_id:
                return await self.evaluate_one(a)
        return None

    async def evaluate_due(self) -> int:
        rows = await self._wh.execute(f"SELECT * FROM {self._table} WHERE enabled = true")
        now = _now()
        checked = 0
        for r in rows:
            alert = self._row_to_alert(r)
            due = alert.last_checked_at is None or (
                alert.last_checked_at <= now - timedelta(minutes=alert.cadence_minutes)
            )
            if not due:
                continue
            try:
                await self.evaluate_one(alert)
                checked += 1
            except Exception:  # noqa: BLE001 - one bad alert must not stop loop
                logger.exception("alert %s evaluation failed", alert.id)
        return checked


class AlertScheduler:
    """In-process loop that evaluates due alerts (mirrors the worker pattern;
    no external scheduler, Principle 8)."""

    def __init__(self, settings: Settings, alerts: AlertService) -> None:
        self._settings = settings
        self._alerts = alerts
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._alerts.evaluate_due()
            except Exception:  # noqa: BLE001 - scheduler must never die
                logger.exception("alert scheduler tick failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=self._settings.alerts_poll_interval_seconds,
                )
            except TimeoutError:
                continue

    def start(self) -> None:
        if self._settings.alerts_enabled:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
