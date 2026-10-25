"""The ``series`` block: chart-ready rows for the frontend. Missing values stay null; no customer ids."""
import json

import pandas as pd
import pytest

from analytics_engine.api_adapter import to_api_result
from analytics_engine.pipeline import run_analysis
from conftest import SAMPLES


def _load(name):
    return {t: pd.read_csv(SAMPLES / name / f"{t}.csv") for t in ("financials", "customers", "products")
            if (SAMPLES / name / f"{t}.csv").exists()}


def _run(name="retail"):
    return run_analysis({"business_id": "b", "business_type": "retail"}, _load(name))


def test_series_has_three_blocks_and_is_strict_json():
    s = _run()["series"]
    assert set(s) == {"financial_monthly", "customer_monthly", "products"}
    json.dumps(s, allow_nan=False)


def test_financial_series_matches_input_hand_check():
    fin = _load("retail")["financials"]
    rows = _run()["series"]["financial_monthly"]
    assert len(rows) == len(fin)
    first = rows[0]
    src = fin.iloc[0]
    assert first["revenue"] == float(src["revenue"])
    assert first["period"] == "2024-01"


def test_series_never_contains_customer_ids():
    text = json.dumps(_run()["series"])
    ids = _load("retail")["customers"]["customer_id"].astype(str).unique()
    assert not any(f'"{i}"' in text for i in ids[:50])
    assert "customer_id" not in text and "top_customers" not in text


def test_missing_table_gives_empty_list_not_zeros():
    data = _load("retail"); data.pop("customers"); data.pop("products")
    s = run_analysis({"business_id": "b", "business_type": "retail"}, data)["series"]
    assert s["customer_monthly"] == [] and s["products"] == [] and s["financial_monthly"]


def test_messy_series_keeps_nulls():
    rows = _run("messy")["series"]["financial_monthly"]
    for r in rows:
        if r["expenses_complete"] is not True:
            assert r["profit"] is None  # profit is never invented when expenses are incomplete


def test_adapter_passes_series_through_and_validates():
    jsonschema = pytest.importorskip("jsonschema")
    res = _run()
    api = to_api_result(res)
    assert api["series"] == res["series"]
    for schema, doc in (("engine-result", res), ("analysis-result", api)):
        sc = json.loads((SAMPLES.parents[1] / "contracts" / f"{schema}.schema.json").read_text())
        assert list(jsonschema.Draft202012Validator(sc).iter_errors(doc)) == []


def test_schema_rejects_bad_series():
    jsonschema = pytest.importorskip("jsonschema")
    sc = json.loads((SAMPLES.parents[1] / "contracts" / "analysis-result.schema.json").read_text())
    api = to_api_result(_run())
    bad = json.loads(json.dumps(api)); bad["series"]["financial_monthly"][0]["period"] = "Jan 2024"
    assert list(jsonschema.Draft202012Validator(sc).iter_errors(bad))
    bad = json.loads(json.dumps(api)); bad["series"]["customers"] = []
    assert list(jsonschema.Draft202012Validator(sc).iter_errors(bad))


def test_failed_run_has_no_series_key():
    res = run_analysis({"business_id": "b"}, {})
    assert "series" not in res
