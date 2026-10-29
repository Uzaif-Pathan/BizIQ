from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def _upload(client, business_id, data_type, name, content, filename=None):
    return client.post(
        f"/api/v1/businesses/{business_id}/imports",
        data={"data_type": data_type},
        files={"file": (filename or name, content, "text/csv")},
    )


def _sample(path):
    return (SAMPLES / path).read_bytes()


def test_upload_clean_file(client, business):
    r = _upload(client, business["id"], "financials", "retail/financials.csv", _sample("retail/financials.csv"),
                "financials.csv")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "completed" and body["data_type"] == "financials"
    assert body["row_count"] == 24 and body["valid_row_count"] == 24
    assert body["error_count"] == 0 and body["warning_count"] == 0
    assert body["business_id"] == business["id"] and isinstance(body["id"], str)


def test_upload_messy_file_reports_issues(client, business):
    r = _upload(client, business["id"], "financials", "m", _sample("messy/financials.csv"), "messy.csv")
    body = r.json()
    assert r.status_code == 201 and body["status"] == "completed_with_warnings"
    assert (body["row_count"], body["valid_row_count"]) == (14, 9)
    issues = client.get(f"/api/v1/businesses/{business['id']}/imports/{body['id']}/issues")
    assert issues.status_code == 200 and len(issues.json()) == body["error_count"] + body["warning_count"]
    only_errors = client.get(
        f"/api/v1/businesses/{business['id']}/imports/{body['id']}/issues", params={"severity": "error"})
    assert len(only_errors.json()) == body["error_count"]
    assert {i["code"] for i in only_errors.json()} == {"invalid_period", "conflicting_duplicates"}


def test_unusable_file_is_recorded_as_failed(client, business):
    r = _upload(client, business["id"], "financials", "x", b"period,costs\n2025-01,5\n", "bad.csv")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed" and body["valid_row_count"] == 0
    issues = client.get(f"/api/v1/businesses/{business['id']}/imports/{body['id']}/issues").json()
    assert issues[0]["code"] == "missing_required_columns"


def test_history_and_single_import(client, business):
    first = _upload(client, business["id"], "financials", "a", _sample("retail/financials.csv"), "a.csv").json()
    second = _upload(client, business["id"], "customers", "b", _sample("retail/customers.csv"), "b.csv").json()
    listing = client.get(f"/api/v1/businesses/{business['id']}/imports").json()
    assert [i["id"] for i in listing] == [second["id"], first["id"]]
    one = client.get(f"/api/v1/businesses/{business['id']}/imports/{first['id']}")
    assert one.status_code == 200 and one.json()["file_name"] == "a.csv"


def test_rejects_non_csv_name_empty_and_bad_type(client, business):
    assert _upload(client, business["id"], "financials", "x", b"period,revenue\n2025-01,1\n", "data.xlsx").status_code == 400
    assert _upload(client, business["id"], "financials", "x", b"", "empty.csv").status_code == 400
    assert _upload(client, business["id"], "inventory", "x", b"a,b\n1,2\n", "x.csv").status_code == 422
    r = client.post(f"/api/v1/businesses/{business['id']}/imports", data={"data_type": "financials"})
    assert r.status_code == 422


def test_unknown_business_and_import_return_404(client, business):
    assert _upload(client, 999, "financials", "x", b"period,revenue\n2025-01,1\n", "x.csv").status_code == 404
    assert client.get("/api/v1/businesses/999/imports").status_code == 404
    assert client.get(f"/api/v1/businesses/{business['id']}/imports/999").status_code == 404
    assert client.get(f"/api/v1/businesses/{business['id']}/imports/999/issues").status_code == 404
