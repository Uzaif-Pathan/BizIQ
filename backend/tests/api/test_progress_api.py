def _analysis(client, business):
    return client.post(f"/api/v1/businesses/{business['id']}/analyses").json()["analysis_id"]


def _url(aid, rid="r-001"):
    return f"/api/v1/analyses/{aid}/recommendations/{rid}/progress"


def test_record_and_read_progress(client, business):
    aid = _analysis(client, business)
    r = client.post(_url(aid), json={"status": "in_progress", "note": "Started renegotiating rent"})
    assert r.status_code == 201
    body = r.json()
    assert body["recommendation_id"] == "r-001" and body["status"] == "in_progress"
    assert body["measured_value"] is None and isinstance(body["id"], str)
    client.post(_url(aid), json={"status": "completed", "measured_value": 18.5, "due_date": "2026-12-31"})
    history = client.get(_url(aid)).json()
    assert [h["status"] for h in history] == ["completed", "in_progress"]
    assert history[0]["measured_value"] == 18.5 and history[0]["due_date"] == "2026-12-31"
    latest = client.get(f"/api/v1/analyses/{aid}/progress").json()
    assert [(p["recommendation_id"], p["status"]) for p in latest] == [("r-001", "completed")]


def test_progress_appears_in_report(client, business):
    aid = _analysis(client, business)
    assert client.get(f"/api/v1/analyses/{aid}/report").json()["recommendation_progress"] == []
    client.post(_url(aid), json={"status": "on_hold"})
    report = client.get(f"/api/v1/analyses/{aid}/report").json()
    assert [p["status"] for p in report["recommendation_progress"]] == ["on_hold"]


def test_validation_and_not_found(client, business):
    aid = _analysis(client, business)
    assert client.post(_url(aid), json={"status": "finished"}).status_code == 422
    assert client.post(_url(aid), json={}).status_code == 422
    assert client.post(_url(aid, "r-999"), json={"status": "completed"}).status_code == 404
    assert client.get(_url(aid, "r-999")).status_code == 404
    assert client.post(_url("nope"), json={"status": "completed"}).status_code == 404
    assert client.get("/api/v1/analyses/nope/progress").status_code == 404
