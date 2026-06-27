"""Contract tests for the customers (tenant) routes."""


def test_customers_list_ok(client):
    r = client.get("/customers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_customer_servers_filtered_by_ownership(client):
    client.post("/servers", json={"name": "a1", "game": "minecraft", "options": {"customer": "cust-a"}})
    client.post("/servers", json={"name": "b1", "game": "minecraft", "options": {"customer": "cust-b"}})
    r = client.get("/customers/cust-a/servers")
    assert r.status_code == 200
    assert [s["name"] for s in r.json()] == ["a1"]
    # the created server carries its owning customer on the spec
    assert r.json()[0]["spec"]["customer"] == "cust-a"
