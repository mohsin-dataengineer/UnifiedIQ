async def test_pin_lifecycle(client):
    created = await client.post(
        "/api/views",
        json={
            "name": "Trips per pickup zip",
            "question": "Trip count by pickup zip",
            "sql": (
                "SELECT pickup_zip, COUNT(*) AS n FROM samples.nyctaxi.trips GROUP BY pickup_zip"
            ),
            "chart_config": {"type": "bar", "x": "pickup_zip", "y": ["n"]},
            "default_view": "bar",
        },
    )
    assert created.status_code == 200
    view = created.json()
    assert view["name"] == "Trips per pickup zip"
    assert view["spec"]["default_view"] == "bar"
    view_id = view["id"]

    listed = await client.get("/api/views")
    assert any(v["id"] == view_id for v in listed.json())

    ran = await client.post(f"/api/views/{view_id}/run")
    assert ran.status_code == 200
    body = ran.json()
    assert body["view"]["id"] == view_id
    assert body["rows"] == [{"k": "a", "v": 1}, {"k": "b", "v": 2}]

    deleted = await client.delete(f"/api/views/{view_id}")
    assert deleted.json() == {"deleted": True}
    assert (await client.get("/api/views")).json() == []


async def test_run_missing_view_returns_404(client):
    resp = await client.post("/api/views/nope/run")
    assert resp.status_code == 404


async def test_update_view_patches_name_and_spec(client):
    created = await client.post(
        "/api/views",
        json={
            "name": "old",
            "question": "q",
            "sql": "SELECT 1 AS v",
            "default_view": "table",
        },
    )
    view_id = created.json()["id"]

    updated = await client.patch(
        f"/api/views/{view_id}",
        json={
            "name": "new name",
            "spec": {
                "x_label": "Month",
                "y_label": "Revenue",
                "colors": ["#4f46e5", "#16a34a"],
                "filter_text": "abc",
                "layout": {"w": 2, "h": 1, "position": 0},
            },
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "new name"
    assert body["spec"]["x_label"] == "Month"
    assert body["spec"]["colors"] == ["#4f46e5", "#16a34a"]
    assert body["spec"]["layout"]["w"] == 2


async def test_invalid_sql_rejected(client):
    resp = await client.post(
        "/api/views",
        json={
            "name": "bad",
            "question": "bad",
            "sql": "SELEKT *",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "SQL_INVALID"
