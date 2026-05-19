import asyncio

from app.config import Settings
from app.models.domain import SessionTurn
from app.services.session_store import SessionStore


async def test_append_is_flushed_by_worker():
    settings = Settings(worker_flush_interval_seconds=0.05)
    store = SessionStore(settings)
    store.start()
    try:
        await store.append(
            SessionTurn(
                session_id="s1",
                user_email="u@x.com",
                role="user",
                content="hi",
            )
        )
        for _ in range(50):
            if await store.load("s1"):
                break
            await asyncio.sleep(0.02)
        loaded = await store.load("s1")
        assert len(loaded) == 1
        assert loaded[0].user_email == "u@x.com"
    finally:
        await store.stop()


async def test_stop_flushes_remaining():
    settings = Settings(worker_flush_interval_seconds=5.0)
    store = SessionStore(settings)
    store.start()
    await store.append(
        SessionTurn(session_id="s2", user_email="u@x.com", role="user", content="bye")
    )
    await store.stop()
    assert len(await store.load("s2")) == 1
