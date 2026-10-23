import json

import jsonschema
import numpy as np
import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine import run_analysis
from analytics_engine.evidence import assess_evidence
from analytics_engine.validation import validate_table

SCHEMA = json.load(open(SAMPLES.parents[1] / "contracts" / "analysis-result.schema.json"))
BIZ = json.load(open(SAMPLES / "businesses.json"))
TABLES = {"retail": ["financials", "customers", "products"], "service": ["financials", "customers"],
          "cold_start": ["financials"], "messy": ["financials"]}


def load(scenario):
    return {t: pd.read_csv(SAMPLES / scenario / f"{t}.csv") for t in TABLES[scenario]}


def run(scenario, **kw):
    return run_analysis(BIZ[scenario], load(scenario), **kw)


def months_fin(n, complete=True, start="2024-01"):
    p = pd.period_range(start, periods=n, freq="M").astype(str)
    return pd.DataFrame({"period": p, "revenue": 1000.0 + np.arange(n), "expenses": 800.0,
                         "expenses_complete": complete})


# ---------- end to end on the sample scenarios -----------------------------
def test_retail_is_complete_high_evidence_and_full_output():
    r = run("retail")
    assert r["status"] == "completed" and r["evidence_level"] == "high"
    assert r["health_score"]["score"] is not None
    assert r["models"]["forecast"]["status"] == "ok"
    assert "revenue" in r["metrics"] and "active_customers" in r["metrics"] and "gross_margin_pct" in r["metrics"]
    assert r["findings"] and r["business_type"] == "retail"


def test_service_has_no_profit_when_expenses_incomplete():
    r = run("service")
    assert r["metrics"]["profit"]["value"] is None
    assert r["metrics"]["revenue_minus_listed_expenses"]["value"] is not None
    assert r["evidence_level"] == "high"  # 12 months + customers


def test_cold_start_is_low_evidence_with_caveated_recommendations():
    r = run("cold_start")
    assert r["evidence_level"] == "low"
    assert r["health_score"]["score"] is None
    assert r["models"]["segmentation"]["status"] == "not_applicable"
    assert r["recommendations"] and all("caveat" in x for x in r["recommendations"])


def test_messy_data_gives_partial_with_errors_reported():
    r = run("messy")
    assert r["status"] == "partial"
    codes = {e["code"] for e in r["validation"]["errors"]}
    assert {"invalid_period", "conflicting_duplicates"} <= codes
    assert r["evidence_level"] != "high"


@pytest.mark.parametrize("scenario", list(TABLES))
def test_result_is_json_serialisable_and_matches_contract_schema(scenario):
    r = run(scenario)
    json.dumps(r, allow_nan=False)  # no NaN / numpy leaks
    jsonschema.validate(r, SCHEMA)


def test_failed_result_matches_schema_too():
    r = run_analysis(BIZ["retail"], {})
    assert r["status"] == "failed"
    jsonschema.validate(r, SCHEMA)


# ---------- robustness: never raises ---------------------------------------
@pytest.mark.parametrize("business,data", [
    (None, None), ({}, None), ({}, "text"), ({}, {}), (None, {"financials": None}),
    ({}, {"financials": pd.DataFrame()}), ({}, {"financials": "not a frame"}),
    ({}, {"financials": pd.DataFrame({"x": [1]})}), (5, {"customers": 3}),
])
def test_never_raises_on_garbage(business, data):
    r = run_analysis(business, data)
    assert r["status"] == "failed" and r["error"]["code"] in {"invalid_input", "no_usable_data"}
    assert r["evidence_level"] == "low" and r["recommendations"] == []


def test_unknown_business_type_warns_and_uses_generic_wording():
    r = run_analysis({"business_id": "x", "business_type": "spaceship"}, load("cold_start"))
    assert any(w["code"] == "unknown_business_type" for w in r["validation"]["warnings"])
    assert r["business_type"] == "other"


def test_customers_only_gives_partial_not_failed():
    r = run_analysis(BIZ["retail"], {"customers": load("retail")["customers"]})
    assert r["status"] == "partial" and r["evidence_level"] == "low"
    assert "active_customers" in r["metrics"] and r["health_score"]["score"] is None
    assert any(w["code"] == "no_financial_data" for w in r["validation"]["warnings"])


def test_a_failing_module_is_skipped_not_fatal(monkeypatch):
    import analytics_engine.pipeline as pl
    monkeypatch.setattr(pl, "forecast_revenue", lambda *a, **k: 1 / 0)
    r = run("retail")
    assert r["status"] == "partial" and r["models"]["forecast"]["status"] == "failed"
    assert any(w["code"] == "module_failed" for w in r["validation"]["warnings"])
    assert r["metrics"] and r["health_score"]["score"] is not None


def test_inputs_are_not_mutated():
    data = load("retail")
    before = {k: v.copy() for k, v in data.items()}
    run_analysis(BIZ["retail"], data)
    for k in data:
        pd.testing.assert_frame_equal(data[k], before[k])


def test_missing_optional_tables_are_not_errors():
    r = run_analysis(BIZ["retail"], {"financials": load("retail")["financials"], "customers": None})
    assert r["status"] == "completed" and r["validation"]["errors"] == []
    assert r["evidence_level"] == "medium"  # 24 months but no customer/product data


def test_deterministic_apart_from_analysis_id():
    a, b = run("retail"), run("retail")
    a.pop("analysis_id"), b.pop("analysis_id")
    assert a == b


# ---------- benchmark status -----------------------------------------------
def bm(metric, value=20.0):
    return {"metric": metric, "value": value, "source": "test", "year": 2025,
            "geography": "MH", "geography_level": "state", "definition": "d"}


def test_benchmark_status_unavailable_available_partial():
    assert run("retail")["benchmark_status"] == "unavailable"
    assert run("retail", benchmarks=[bm("profit_margin_pct")])["benchmark_status"] == "partial"
    both = run("retail", benchmarks=[bm("profit_margin_pct"), bm("gross_margin_pct")])
    assert both["benchmark_status"] == "available"
    assert {c["basis"] for c in both["health_score"]["components"]} >= {"benchmark"}


def test_non_matching_benchmark_is_ignored():
    r = run("retail", benchmarks=[bm("net_margin"), {"metric": "profit_margin_pct", "value": "n/a"}])
    assert r["benchmark_status"] == "unavailable"


# ---------- evidence rules --------------------------------------------------
def rep(df, name="financials"):
    return validate_table(df, name)


def cus_ok():
    return rep(pd.DataFrame({"period": ["2025-01"], "customer_id": ["C1"], "amount_spent": [10.0]}), "customers")


@pytest.mark.parametrize("months,side,expected", [
    (3, True, "low"), (5, True, "low"), (6, False, "medium"), (11, True, "medium"),
    (12, False, "medium"), (12, True, "high"), (24, True, "high"),
])
def test_evidence_thresholds(months, side, expected):
    out = assess_evidence(months, rep(months_fin(max(months, 1))), cus_ok() if side else None, None)
    assert out["level"] == expected and out["reasons"]


def test_financial_errors_cap_evidence_at_medium():
    df = pd.concat([months_fin(14), pd.DataFrame({"period": ["2025-13"], "revenue": [1.0], "expenses": [1.0],
                                                  "expenses_complete": [True]})], ignore_index=True)
    out = assess_evidence(14, rep(df), cus_ok(), None)
    assert out["level"] == "medium" and "validation errors" in " ".join(out["reasons"])


def test_unusable_financials_are_low():
    assert assess_evidence(0, None, cus_ok(), None)["level"] == "low"
