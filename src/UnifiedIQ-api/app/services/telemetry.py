"""TelemetryLogger - fire-and-forget event logging via an async queue.

Same batched-flush pattern as SessionStore (Principle 5). Events also emit a
structured JSON log line so the standard observability fields stay queryable
even before a durable telemetry sink is wired.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.config import Settings
from app.models.domain import TelemetryEvent

logger = logging.getLogger("telemetry")


class TelemetryLogger:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._events: list[TelemetryEvent] = []
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def log(self, event: TelemetryEvent) -> None:
        await self._queue.put(event)

    def _persist(self, batch: list[TelemetryEvent]) -> None:
        for event in batch:
            self._events.append(event)
            logger.info(
                event.event_type,
                extra={
                    "request_id": event.request_id,
                    "user_email": event.user_email,
                    "latency_ms": event.latency_ms,
                    "tokens_in": event.tokens_in,
                    "tokens_out": event.tokens_out,
                },
            )

    async def _drain_batch(self) -> list[TelemetryEvent]:
        batch: list[TelemetryEvent] = [await self._queue.get()]
        while len(batch) < self._settings.worker_flush_max_items and not self._queue.empty():
            batch.append(self._queue.get_nowait())
        return batch

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                batch = await asyncio.wait_for(
                    self._drain_batch(),
                    timeout=self._settings.worker_flush_interval_seconds,
                )
            except TimeoutError:
                continue
            try:
                self._persist(batch)
            except Exception:  # noqa: BLE001 - never let a write kill the worker
                logger.exception("telemetry flush failed")

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        remaining: list[TelemetryEvent] = []
        while not self._queue.empty():
            remaining.append(self._queue.get_nowait())
        if remaining:
            self._persist(remaining)
