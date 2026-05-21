async def test_canvas_lifecycle(client):
    created = await client.post("/api/canvases", json={"name": "Sales Review"})
    assert created.status_code == 200
    canvas = created.json()
    assert canvas["name"] == "Sales Review"
    assert canvas["status"] == "draft"
    cid = canvas["id"]

    listed = await client.get("/api/canvases")
    assert any(c["id"] == cid for c in listed.json())

    renamed = await client.patch(f"/api/canvases/{cid}", json={"name": "Sales — Q1"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Sales — Q1"

    deleted = await client.delete(f"/api/canvases/{cid}")
    assert deleted.json() == {"deleted": True}
    assert all(c["id"] != cid for c in (await client.get("/api/canvases")).json())


async def test_publish_snapshots_canvas_and_views(client):
    canvas = (await client.post("/api/canvases", json={"name": "Ops"})).json()
    cid = canvas["id"]

    view = (
        await client.post(
            "/api/views",
            json={
                "name": "Pinned KPI",
                "question": "How many trips",
                "sql": "SELECT COUNT(*) AS n FROM samples.nyctaxi.trips",
                "default_view": "kpi",
                "canvas_id": cid,
            },
        )
    ).json()
    assert view["spec"]["canvas_id"] == cid

    publish = await client.post(f"/api/canvases/{cid}/publish")
    assert publish.status_code == 200
    published = publish.json()
    assert published["status"] == "published"
    assert published["source_canvas_id"] == cid
    pid = published["id"]

    # The original draft survives.
    canvases = (await client.get("/api/canvases")).json()
    ids = {c["id"] for c in canvases}
    assert cid in ids and pid in ids

    # Each canvas owns its own view copy.
    draft_views = (await client.get(f"/api/views?canvas_id={cid}")).json()
    pub_views = (await client.get(f"/api/views?canvas_id={pid}")).json()
    assert len(draft_views) == 1
    assert len(pub_views) == 1
    assert draft_views[0]["id"] != pub_views[0]["id"]


async def test_published_canvas_is_immutable(client):
    canvas = (await client.post("/api/canvases", json={"name": "X"})).json()
    cid = canvas["id"]
    view = (
        await client.post(
            "/api/views",
            json={
                "name": "v",
                "question": "q",
                "sql": "SELECT 1 AS v",
                "canvas_id": cid,
            },
        )
    ).json()

    pub = (await client.post(f"/api/canvases/{cid}/publish")).json()
    pid = pub["id"]
    pub_view_id = ((await client.get(f"/api/views?canvas_id={pid}")).json())[0]["id"]

    # Rename forbidden
    r = await client.patch(f"/api/canvases/{pid}", json={"name": "nope"})
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"

    # Delete forbidden
    r = await client.delete(f"/api/canvases/{pid}")
    assert r.status_code == 403

    # View edits forbidden
    r = await client.patch(f"/api/views/{pub_view_id}", json={"name": "renamed"})
    assert r.status_code == 403

    r = await client.delete(f"/api/views/{pub_view_id}")
    assert r.status_code == 403

    # Draft remains editable
    r = await client.patch(f"/api/views/{view['id']}", json={"name": "edited"})
    assert r.status_code == 200
    assert r.json()["name"] == "edited"


async def test_pin_without_canvas_routes_to_default(client):
    # No canvas_id given - server should create + assign a default canvas.
    created = await client.post(
        "/api/views",
        json={"name": "Orphan", "question": "q", "sql": "SELECT 1 AS v"},
    )
    assert created.status_code == 200
    cid = created.json()["spec"]["canvas_id"]
    assert cid

    canvases = (await client.get("/api/canvases")).json()
    assert any(c["id"] == cid and c["status"] == "draft" for c in canvases)
