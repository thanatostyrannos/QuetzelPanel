"""API-level tests through FastAPI TestClient against a fresh MockProvider."""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["provider"] == "MockProvider"


def test_games_lists_catalog(client):
    r = client.get("/games")
    assert r.status_code == 200
    ids = [g["id"] for g in r.json()["games"]]
    assert "minecraft" in ids and "valheim" in ids
    assert len(ids) >= 2


def test_create_get_list_delete_lifecycle(client):
    # create
    r = client.post("/servers", json={"name": "mc-demo", "game": "minecraft", "options": {"version": "1.21.1"}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "mc-demo"
    assert body["spec"]["version"] == "1.21.1"
    assert body["status"]["phase"] in ("Pending", "Provisioning", "Running")

    # get
    r = client.get("/servers/mc-demo")
    assert r.status_code == 200
    assert r.json()["name"] == "mc-demo"

    # list
    r = client.get("/servers")
    assert r.status_code == 200
    assert any(s["name"] == "mc-demo" for s in r.json())

    # delete
    r = client.delete("/servers/mc-demo")
    assert r.status_code == 204

    # gone
    assert client.get("/servers/mc-demo").status_code == 404


def test_duplicate_returns_409(client):
    client.post("/servers", json={"name": "dup", "game": "minecraft", "options": {}})
    r = client.post("/servers", json={"name": "dup", "game": "minecraft", "options": {}})
    assert r.status_code == 409


def test_unknown_game_returns_400(client):
    r = client.post("/servers", json={"name": "x", "game": "halo", "options": {}})
    assert r.status_code == 400


def test_invalid_name_returns_422(client):
    r = client.post("/servers", json={"name": "Bad Name!", "game": "minecraft", "options": {}})
    assert r.status_code == 422


def test_delete_missing_returns_404(client):
    assert client.delete("/servers/ghost").status_code == 404


def test_empty_list_initially(client):
    assert client.get("/servers").json() == []
