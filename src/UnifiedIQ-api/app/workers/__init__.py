"""Background worker start/stop hooks, registered in the app lifespan."""

from __future__ import annotations

from app.deps import AppState


def start_workers(state: AppState) -> None:
    state.sessions.start()
    state.telemetry.start()
    state.alert_scheduler.start()


async def stop_workers(state: AppState) -> None:
    await state.sessions.stop()
    await state.telemetry.stop()
    await state.alert_scheduler.stop()
