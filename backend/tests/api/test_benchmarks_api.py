def test_benchmarks_unavailable_without_database(client, business):
    r = client.get(f"/api/v1/businesses/{business['id']}/benchmarks")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unavailable" and body["items"] == []
    assert body["business_id"] == business["id"]
    assert any("profit" in n for n in body["notes"])  # the context-only warning is always shown


def test_benchmarks_missing_business_is_404(client):
    r = client.get("/api/v1/businesses/999999999/benchmarks")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
