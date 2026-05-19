async def test_health_shallow(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["dependencies"] == {}


async def test_health_deep_probes_warehouse(client):
    resp = await client.get("/api/health?deep=true")
    assert resp.status_code == 200
    assert resp.json()["dependencies"] == {"warehouse": True}


async def test_me_returns_current_user(client):
    resp = await client.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "tester@unifiediq.dev"
    assert body["name"] == "Tester"
