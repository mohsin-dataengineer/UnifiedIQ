import re

from app.models.responses import SQLGenerationResponse


def _events(body: str) -> list[str]:
    return re.findall(r"^event: (\w+)$", body, flags=re.MULTILINE)


async def test_stream_data_intent_event_sequence(client, state):
    resp = await client.post("/api/chat/stream", json={"question": "revenue by region"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _events(resp.text)
    assert events[0] == "thinking"
    assert "sql" in events
    assert "data" in events
    assert events[-1] == "done"
    assert "error" not in events
    assert "SELECT region, revenue FROM sales" in resp.text

    turns = await state.sessions.load(
        # session id is echoed in the done metadata
        re.search(r'"session_id": "(\w+)"', resp.text).group(1)
    )
    assert [t.role for t in turns] == ["user", "assistant"]


async def test_stream_clarify_skips_sql(client, state):
    state.llm.plan = SQLGenerationResponse(intent="clarify", clarifying_question="Which period?")
    resp = await client.post("/api/chat/stream", json={"question": "revenue"})
    events = _events(resp.text)
    assert "sql" not in events
    assert "data" in events
    assert events[-1] == "done"
    assert "Which period?" in resp.text


async def test_stream_terminates_with_error_on_invalid_sql(client, state):
    state.llm.plan = SQLGenerationResponse(intent="data", sql="SELEKT bad FROM")
    resp = await client.post("/api/chat/stream", json={"question": "bad"})
    events = _events(resp.text)
    assert events[-1] == "error"
    assert '"code": "SQL_INVALID"' in resp.text
    # never a half-open stream: error is the terminal event
    assert events.count("done") == 0
