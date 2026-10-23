from uuid import uuid4

from app.api.deps import get_analysis_repo
from app.main import app
from app.schemas.analysis import AnalysisResult
from app.services.analytics_service import get_analytics_engine


def _broken_engine(business):
    raise RuntimeError("engine exploded")


def _bad_shape_engine(business):
    return {"metrics": {}}  # missing required contract fields


def test_request_analysis_completed(client, business):
    r = client.post(f"/api/v1/businesses/{business['id']}/analyses")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed"
    assert body["business_id"] == business["id"]
    assert body["evidence_level"] == "medium"
    assert body["benchmark_status"] == "unavailable"
    assert body["completed_at"] is not None
    # The response must satisfy the shared contract.
    AnalysisResult.model_validate(body)


def test_get_analysis_findings_and_recommendations(client, business):
    aid = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()["analysis_id"]
    assert client.get(f"/api/v1/analyses/{aid}").json()["analysis_id"] == aid
    findings = client.get(f"/api/v1/analyses/{aid}/findings").json()
    recs = client.get(f"/api/v1/analyses/{aid}/recommendations").json()
    assert findings[0]["finding_id"] == "f-001"
    assert recs[0]["supporting_finding_ids"] == ["f-001"]


def test_analysis_for_missing_business(client):
    r = client.post(f"/api/v1/businesses/{uuid4()}/analyses")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_missing_analysis_returns_404(client):
    for suffix in ("", "/findings", "/recommendations", "/report"):
        assert client.get(f"/api/v1/analyses/nope{suffix}").status_code == 404


def test_history_newest_first_and_business_status_updates(client, business):
    first = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()
    second = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()
    history = client.get(f"/api/v1/businesses/{business['id']}/analyses").json()
    assert [h["analysis_id"] for h in history] == [second["analysis_id"], first["analysis_id"]]
    assert client.get(f"/api/v1/businesses/{business['id']}").json()[
        "latest_analysis_status"
    ] == "completed"


def test_failed_run_is_saved_and_consistent(client, business):
    app.dependency_overrides[get_analytics_engine] = lambda: _broken_engine
    r = client.post(f"/api/v1/businesses/{business['id']}/analyses")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_message"]
    assert "exploded" not in body["error_message"]  # internal details are not leaked
    assert body["metrics"]["revenue"] is None
    assert body["findings"] == [] and body["recommendations"] == []
    assert body["evidence_level"] == "insufficient"
    assert body["benchmark_status"] == "unavailable"
    AnalysisResult.model_validate(body)
    # Still stored, and the business shows the failed status.
    assert client.get(f"/api/v1/analyses/{body['analysis_id']}").json()["status"] == "failed"
    assert client.get(f"/api/v1/businesses/{business['id']}").json()[
        "latest_analysis_status"
    ] == "failed"


def test_engine_returning_wrong_shape_becomes_failed_run(client, business):
    app.dependency_overrides[get_analytics_engine] = lambda: _bad_shape_engine
    body = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()
    assert body["status"] == "failed"


def test_report_for_completed_analysis(client, business):
    aid = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()["analysis_id"]
    r = client.get(f"/api/v1/analyses/{aid}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["business"]["id"] == business["id"]
    assert body["analysis"]["analysis_id"] == aid
    assert "generated_at" in body


def test_report_for_failed_analysis_is_conflict(client, business):
    app.dependency_overrides[get_analytics_engine] = lambda: _broken_engine
    aid = client.post(f"/api/v1/businesses/{business['id']}/analyses").json()["analysis_id"]
    r = client.get(f"/api/v1/analyses/{aid}/report")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"
