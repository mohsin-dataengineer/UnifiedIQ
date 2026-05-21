async def test_memory_lifecycle(client):
    created = await client.post(
        "/api/memory",
        json={"value": "Our fiscal year starts in April"},
    )
    assert created.status_code == 200
    m = created.json()
    assert m["value"] == "Our fiscal year starts in April"
    mid = m["id"]

    listed = await client.get("/api/memory")
    assert any(x["id"] == mid for x in listed.json())

    deleted = await client.delete(f"/api/memory/{mid}")
    assert deleted.json() == {"deleted": True}
    assert (await client.get("/api/memory")).json() == []


async def test_memory_validation_rejects_empty(client):
    resp = await client.post("/api/memory", json={"value": ""})
    assert resp.status_code == 422
