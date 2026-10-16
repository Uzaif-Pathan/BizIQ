from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app

client = TestClient(app)


def test_root_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["application"] == "BizIQ"


def test_v1_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_not_found_uses_error_format():
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert "message" in body["error"]


class _Item(BaseModel):
    name: str


@app.post("/_test/validation")
def _validation_route(item: _Item) -> dict:
    return {"ok": True}


def test_validation_error_format():
    r = client.post("/_test/validation", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"][0]["field"] == "name"


def test_cors_allows_frontend_origin():
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
