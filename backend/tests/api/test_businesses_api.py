

def test_create_and_get_business(client):
    r = client.post(
        "/api/v1/businesses",
        json={
            "name": "  Sharma Traders ",
            "industry": "Grocery",
            "business_type": "retail",
            "goals": ["Reduce expenses"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Sharma Traders"
    assert body["country"] == "India"
    assert body["goals"] == ["Reduce expenses"]
    assert body["latest_analysis_status"] is None

    got = client.get(f"/api/v1/businesses/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_create_business_validation_error(client):
    r = client.post("/api/v1/businesses", json={"name": "A", "industry": "x"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_list_businesses(client, business):
    r = client.get("/api/v1/businesses")
    assert r.status_code == 200
    assert [b["id"] for b in r.json()] == [business["id"]]


def test_list_pagination_limits_validated(client):
    assert client.get("/api/v1/businesses?limit=0").status_code == 422


def test_update_business_partial(client, business):
    r = client.patch(f"/api/v1/businesses/{business['id']}", json={"city": "Aurangabad"})
    assert r.status_code == 200
    assert r.json()["city"] == "Aurangabad"
    assert r.json()["name"] == "Sharma Traders"  # untouched


def test_update_goals(client, business):
    r = client.patch(
        f"/api/v1/businesses/{business['id']}", json={"goals": ["Grow revenue"]}
    )
    assert r.json()["goals"] == ["Grow revenue"]


def test_update_business_empty_body_rejected(client, business):
    r = client.patch(f"/api/v1/businesses/{business['id']}", json={})
    assert r.status_code == 422


def test_missing_business_returns_404_format(client):
    r = client.get(f"/api/v1/businesses/999999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    assert client.patch(f"/api/v1/businesses/999999999", json={"city": "X"}).status_code == 404


def test_invalid_business_id_is_validation_error(client):
    r = client.get("/api/v1/businesses/not-a-number")
    assert r.status_code == 422
