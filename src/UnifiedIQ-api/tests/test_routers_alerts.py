async def test_alert_lifecycle(client):
    created = await client.post(
        "/api/alerts",
        json={"question": "Alert me when daily signups drop below 1000"},
    )
    assert created.status_code == 200
    alert = created.json()
    assert alert["title"] == "Low signups"
    assert alert["comparator"] == "lt"
    assert alert["threshold"] == 1000
    alert_id = alert["id"]

    listed = await client.get("/api/alerts")
    assert any(a["id"] == alert_id for a in listed.json())

    ran = await client.post(f"/api/alerts/{alert_id}/run")
    assert ran.status_code == 200
    assert ran.json()["last_state"] == "breached"

    notes = await client.get("/api/notifications")
    assert len(notes.json()) == 1
    assert notes.json()[0]["title"] == "Low signups"

    deleted = await client.delete(f"/api/alerts/{alert_id}")
    assert deleted.json() == {"deleted": True}
    assert (await client.get("/api/alerts")).json() == []


async def test_run_missing_alert_404(client):
    resp = await client.post("/api/alerts/nope/run")
    assert resp.status_code == 404


async def test_user_overrides_apply(client):
    resp = await client.post(
        "/api/alerts",
        json={
            "question": "Alert me when daily signups drop below 1000",
            "channel": "email",
            "recipient": "ops@example.com",
            "cadence_minutes": 30,
        },
    )
    assert resp.status_code == 200
    a = resp.json()
    assert a["channel"] == "email"
    assert a["recipient"] == "ops@example.com"
    assert a["cadence_minutes"] == 30


async def test_email_recipient_required(client):
    resp = await client.post(
        "/api/alerts",
        json={"question": "anything", "channel": "email"},
    )
    assert resp.status_code == 422
    assert "Recipient is required" in resp.json()["message"]


async def test_invalid_email_rejected(client):
    resp = await client.post(
        "/api/alerts",
        json={"question": "anything", "channel": "email", "recipient": "not-an-email"},
    )
    assert resp.status_code == 422


async def test_slack_recipient_format(client):
    resp = await client.post(
        "/api/alerts",
        json={"question": "anything", "channel": "slack", "recipient": "alerts"},
    )
    assert resp.status_code == 422
    ok = await client.post(
        "/api/alerts",
        json={"question": "anything", "channel": "slack", "recipient": "#alerts"},
    )
    assert ok.status_code == 200
    assert ok.json()["channel"] == "slack"
    assert ok.json()["recipient"] == "#alerts"
