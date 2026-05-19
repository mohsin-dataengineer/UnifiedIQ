from app.models.responses import SQLGenerationResponse


async def test_chat_data_intent_runs_sql_and_summarizes(client, state):
    resp = await client.post("/api/chat", json={"question": "revenue by region"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "data"
    assert body["sql"] == "SELECT region, revenue FROM sales"
    assert body["data"][0]["region"] == "West"
    assert "West" in body["answer"]
    assert body["session_id"]

    turns = await state.sessions.load(body["session_id"])
    assert [t.role for t in turns] == ["user", "assistant"]


async def test_chat_clarify_intent_skips_warehouse(client, state):
    state.llm.plan = SQLGenerationResponse(
        intent="clarify", clarifying_question="Which time range?"
    )
    resp = await client.post("/api/chat", json={"question": "revenue"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "clarify"
    assert body["answer"] == "Which time range?"
    assert body["data"] == []


async def test_chat_rejects_invalid_sql(client, state):
    state.llm.plan = SQLGenerationResponse(intent="data", sql="SELEKT oops FROM")
    resp = await client.post("/api/chat", json={"question": "bad"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "SQL_INVALID"


async def test_validation_error_uses_stable_code(client):
    resp = await client.post("/api/chat", json={})
    assert resp.status_code == 422
    assert resp.json()["code"] == "BAD_REQUEST"
