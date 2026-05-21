async def test_verify_returns_agree_when_alt_matches(client):
    resp = await client.post(
        "/api/chat/verify",
        json={
            "question": "Sum revenue by region",
            "original_sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # FakeLLM + FakeWarehouse return identical rows for both queries -> agree.
    assert body["verdict"] == "agree"
    assert body["confidence"] > 0.9
    assert body["original_value"] == 120.0
    assert body["alternative_value"] == 120.0
    assert body["alternative_approach"]
    assert "CTE" in body["alternative_sql"] or "WITH" in body["alternative_sql"]


async def test_verify_rejects_bad_original_sql(client):
    resp = await client.post(
        "/api/chat/verify",
        json={
            "question": "anything",
            "original_sql": "SELEKT * FROM",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "SQL_INVALID"


async def test_verify_inconclusive_when_alt_equals_original(client, state):
    # Force the fake LLM to "echo" the original SQL as the alternative.
    from app.models.responses import AlternativeSQLResponse

    state.llm.alt_sql = AlternativeSQLResponse(
        alternative_sql="SELECT region, SUM(revenue) FROM sales GROUP BY region",
        approach="(no real alternative)",
    )
    resp = await client.post(
        "/api/chat/verify",
        json={
            "question": "Sum revenue by region",
            "original_sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "inconclusive"
    assert "identical" in body["rationale"].lower()
