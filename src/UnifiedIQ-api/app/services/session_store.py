"""SessionStore - fire-and-forget session persistence via an async queue.

Appends are enqueued and flushed by a background worker in batches of
N items or every T seconds, whichever comes first (Architectural Principle 5).
The dev sink is in-process and keyed by session_id; rows carry user_email for
logical multi-tenancy (Principle 7). A durable sink (Postgres/warehouse) is a
localized swap of `_persist`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import defaultdict

from app.config import Settings
from app.models.domain import SessionTurn

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[SessionTurn] = asyncio.Queue()
        self._store: dict[str, list[SessionTurn]] = defaultdict(list)
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def append(self, turn: SessionTurn) -> None:
        await self._queue.put(turn)

    async def load(self, session_id: str) -> list[SessionTurn]:
        return list(self._store.get(session_id, []))

    def _persist(self, batch: list[SessionTurn]) -> None:
        for turn in batch:
            self._store[turn.session_id].append(turn)

    async def _drain_batch(self) -> list[SessionTurn]:
        batch: list[SessionTurn] = [await self._queue.get()]
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
                logger.exception("session flush failed")

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        # Best-effort flush of anything still queued at shutdown.
        remaining: list[SessionTurn] = []
        while not self._queue.empty():
            remaining.append(self._queue.get_nowait())
        if remaining:
            self._persist(remaining)
