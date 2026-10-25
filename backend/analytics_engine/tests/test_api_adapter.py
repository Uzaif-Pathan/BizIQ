import copy
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine import run_analysis
from analytics_engine.api_adapter import (EngineRunFailed, business_to_engine_input, run_for_service,
                                          to_api_result, to_service_output)

ROOT = SAMPLES.parents[1]
BIZ = json.loads((SAMPLES / "businesses.json").read_text())
TABLES = {"retail": ["financials", "customers", "products"], "service": ["financials", "customers"],
          "cold_start": ["financials"], "messy": ["financials"]}


def native(scenario):
    return run_analysis(BIZ[scenario], {t: pd.read_csv(SAMPLES / scenario / f"{t}.csv") for t in TABLES[scenario]})


def metric(value, **kw):
    return {"value": value, "unit": "INR", "period": "2025-01/2025-12", "formula": "f", **kw}


def fake(**over):
    """A small hand-built native result (independent of the sample data)."""
    r = {"analysis_id": "A1", "business_id": "B1", "status": "completed", "evidence_level": "medium",
         "evidence_notes": ["7 months of revenue data; 12 are needed for high evidence."],
         "benchmark_status": "unavailable", "error": None, "engine_version": "9.9.9",
         "validation": {"errors": [], "warnings": [], "datasets": {}},
         "metrics": {"revenue": metric(1000.0), "expenses": metric(None, reason="expense definition unknown"),
                     "profit": metric(None, reason="expense definition unknown"),
                     "profit_margin_pct": metric(None, unit="percent", reason="expense definition unknown"),
                     "revenue_mom_pct": metric(4.5, unit="percent")},
         "findings": [], "recommendations": [], "health_score": {"score": None, "limitations": ["Not enough data."]},
         "models": {"forecast": {"status": "skipped_insufficient_data", "mae": None, "rmse": None,
                                 "details": {"reason": "Needs at least 9 months."}},
                    "segmentation": {"status": "not_applicable", "mae": None, "rmse": None,
                                     "details": {"reason": "No customer-level data."}}},
         "data_coverage": {"financials": {"months_with_revenue": 7}}}
    r.update(over)
    return r


def F(id_, type_, severity="medium", metric_="m", value=1.5, evidence="Evidence.", comparison=None):
    return {"id": id_, "type": type_, "metric": metric_, "value": value, "comparison": comparison,
            "evidence": evidence, "severity": severity}


def pydantic_ok(d):
    pytest.importorskip("pydantic")
    try:
        from app.schemas.analysis import AnalysisResult
    except ImportError:
        pytest.skip("backend app package not importable")
    from pydantic import ValidationError
    try:
        AnalysisResult(**d)
        return True
    except ValidationError:
        return False


@pytest.fixture(scope="module")
def validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft202012Validator(json.loads((ROOT / "contracts" / "analysis-result.schema.json").read_text()))


# ---------------- real scenarios satisfy BOTH contract definitions -----------------------------------
@pytest.mark.parametrize("scenario", list(TABLES))
def test_real_output_matches_json_schema_and_backend_pydantic_model(validator, scenario):
    api = to_api_result(native(scenario))
    assert list(validator.iter_errors(api)) == []
    assert pydantic_ok(api)
    json.dumps(api, allow_nan=False)


def test_failed_run_matches_both_contracts(validator):
    api = to_api_result(run_analysis(BIZ["retail"], {"financials": None}))
    assert api["status"] == "failed" and api["evidence_level"] == "insufficient" and api["error_message"]
    assert list(validator.iter_errors(api)) == [] and pydantic_ok(api)
    assert all(v is None for v in api["metrics"].values())


def test_nothing_is_invented_or_lost_in_translation():
    raw = native("retail")
    api = to_api_result(raw)
    assert [f["finding_id"] for f in api["findings"]] == [f["id"] for f in raw["findings"]]
    ids = {f["finding_id"] for f in api["findings"]}
    assert len(api["recommendations"]) == len(raw["recommendations"])
    assert all(r["supporting_finding_ids"] and set(r["supporting_finding_ids"]) <= ids for r in api["recommendations"])
    assert api["health_score"] == raw["health_score"] and api["models"] == raw["models"]
    assert api["validation"] == raw["validation"] and api["evidence_level"] == raw["evidence_level"]


def test_missing_values_stay_null_never_zero():
    api = to_api_result(native("cold_start"))
    assert api["metrics"]["profit"] is None and api["metrics"]["profit_margin"] is None
    assert api["metric_details"]["profit"]["reason"]
    assert 0 not in [v for k, v in api["metrics"].items() if k in ("profit", "profit_margin", "expenses")]


# ---------------- field mapping (hand-built input) ------------------------------------------------------
def test_metrics_are_flat_numbers_with_profit_margin_alias_and_details_kept():
    api = to_api_result(fake())
    assert api["metrics"]["revenue"] == 1000.0 and api["metrics"]["revenue_mom_pct"] == 4.5
    assert set(("revenue", "expenses", "profit", "profit_margin")) <= set(api["metrics"])
    assert "profit_margin_pct" not in api["metrics"]
    assert api["metric_details"]["profit_margin"]["reason"] == "expense definition unknown"
    assert api["metric_details"]["revenue"]["unit"] == "INR"


@pytest.mark.parametrize("sev,expected", [("info", "info"), ("low", "info"), ("medium", "warning"), ("high", "critical")])
def test_severity_mapping(sev, expected):
    assert to_api_result(fake(findings=[F("FIN-X", "loss_months", sev)]))["findings"][0]["severity"] == expected


@pytest.mark.parametrize("fid,ftype,category", [
    ("FIN-MARGIN", "profit_margin_level", "financial"), ("CUS-REPEAT", "repeat_customers", "customer"),
    ("PRD-CONC", "product_concentration", "product"), ("FIN-REVTREND", "revenue_trend_decreasing", "trend"),
    ("FIN-EXPDEF", "expense_definition_incomplete", "data_quality"), ("CUS-REVIEW", "data_needs_review", "data_quality"),
    ("PRD-COVERAGE", "product_data_coverage_low", "data_quality"),
])
def test_category_mapping(fid, ftype, category):
    assert to_api_result(fake(findings=[F(fid, ftype)]))["findings"][0]["category"] == category


def test_finding_fields_and_per_product_titles():
    f = F("PRD-DECLINE-P06", "product_revenue_declining", "low", "revenue_trend_pct_per_month", -3.78,
          "Revenue of 'Tea (250g)' is falling.", comparison="rule of thumb")
    out = to_api_result(fake(findings=[f]))["findings"][0]
    assert out["title"] == "Product revenue is declining: Tea (250g)" and out["category"] == "product"
    assert out["description"] == "Revenue of 'Tea (250g)' is falling."
    assert out["metric_name"] == "revenue_trend_pct_per_month" and out["metric_value"] == -3.78
    assert out["evidence"] == ["revenue_trend_pct_per_month = -3.78", "Reference: rule of thumb"]
    unknown = to_api_result(fake(findings=[F("FIN-Z", "brand_new_type")]))["findings"][0]
    assert unknown["title"] == "Brand new type"


def test_recommendation_mapping():
    rec = {"id": "REC-LOSS", "rule_id": "LOSS", "finding_ids": ["A", "B"], "issue": "Profit is thin.",
           "supporting_metric": "profit_margin_pct", "evidence": "Because.", "action": "Do x.", "priority": "high",
           "kpi": "Margin", "expected_direction": {"metric": "profit_margin_pct", "direction": "increase"},
           "rationale": "Generated by rule LOSS.", "caveat": "Limited data."}
    out = to_api_result(fake(recommendations=[rec]))["recommendations"][0]
    assert out["recommendation_id"] == "REC-LOSS" and out["supporting_finding_ids"] == ["A", "B"]
    assert out["reason"] == "Generated by rule LOSS." and out["expected_direction"] == "increase"
    assert out["title"] == "Profit is thin" and out["issue"] == "Profit is thin." and out["caveat"] == "Limited data."
    rec["expected_direction"] = None
    assert to_api_result(fake(recommendations=[rec]))["recommendations"][0]["expected_direction"] is None


# ---------------- status, evidence, limitations -----------------------------------------------------------
def test_partial_becomes_completed_but_is_flagged_and_explained():
    api = to_api_result(fake(status="partial"))
    assert api["status"] == "completed" and api["engine_status"] == "partial"
    assert any("validation errors" in l for l in api["limitations"])
    assert to_api_result(fake(status="completed"))["engine_status"] == "completed"


def test_failed_gets_insufficient_evidence_and_message():
    api = to_api_result(fake(status="failed", error={"code": "no_usable_data", "message": "No usable data."}))
    assert api["status"] == "failed" and api["error_message"] == "No usable data."
    assert api["error_code"] == "no_usable_data" and api["evidence_level"] == "insufficient"
    api2 = to_api_result(fake(status="failed", error=None))
    assert api2["error_message"]  # never empty: the contract requires it


def test_limitations_explain_the_gaps_without_duplicates():
    lim = to_api_result(fake())["limitations"]
    text = " | ".join(lim)
    assert "7 months of revenue data" in text and "Profit is not available: expense definition unknown" in text
    assert "Revenue forecast: Needs at least 9 months." in text and "Health score: Not enough data." in text
    assert "Benchmark comparison is unavailable" in text
    assert "Customer segmentation" not in text           # not_applicable is not a problem to report
    assert len(lim) == len(set(lim))
    high = to_api_result(fake(evidence_level="high", benchmark_status="available"))["limitations"]
    assert not any("months of revenue" in l or "Benchmark" in l for l in high)


# ---------------- service integration helpers --------------------------------------------------------------
def test_service_output_drops_keys_the_service_supplies_itself():
    out = to_service_output(fake())
    assert not set(out) & {"analysis_id", "business_id", "status", "created_at", "completed_at"}
    assert {"metrics", "findings", "recommendations", "evidence_level", "benchmark_status"} <= set(out)


def test_service_output_raises_for_failed_runs_with_the_reason():
    with pytest.raises(EngineRunFailed) as e:
        to_service_output(fake(status="failed", error={"code": "no_usable_data", "message": "No usable data."}))
    assert e.value.code == "no_usable_data" and e.value.message == "No usable data."


def test_service_output_can_build_the_backend_model_exactly_like_analysis_service_does():
    pytest.importorskip("pydantic")
    try:
        from app.schemas.analysis import AnalysisResult, AnalysisStatus
    except ImportError:
        pytest.skip("backend app package not importable")
    out = to_service_output(native("retail"))
    r = AnalysisResult(analysis_id="x", business_id="y", status=AnalysisStatus.COMPLETED, created_at="2026-01-01T00:00:00Z",
                       completed_at="2026-01-01T00:00:01Z", **out)   # same call as app/services/analysis_service.py
    assert r.evidence_level.value == "high" and r.findings and r.metrics.revenue


def test_business_mapping_from_dict_and_object_with_enums():
    class T:                         # mimics a str Enum such as BusinessType.RETAIL
        value = "manufacturing"
    biz = SimpleNamespace(id="u-1", business_type=T(), industry="steel", city="Pune", district=None, state="MH")
    out = business_to_engine_input(biz)
    assert out == {"business_id": "u-1", "business_type": "other", "industry": "steel", "location": "Pune, MH"}
    assert business_to_engine_input({"business_id": "b", "business_type": "retail"})["business_type"] == "retail"
    assert business_to_engine_input({"business_type": "Service "})["business_type"] == "service"
    for odd in ("hybrid", "other", "", None, "restaurant"):
        assert business_to_engine_input({"business_type": odd})["business_type"] == "other"


def test_run_for_service_end_to_end_and_failure():
    biz = {"id": "b-1", "business_type": "retail", "industry": "grocery", "state": "MH"}
    out = run_for_service(biz, {t: pd.read_csv(SAMPLES / "retail" / f"{t}.csv") for t in TABLES["retail"]})
    assert out["evidence_level"] == "high" and out["findings"]
    with pytest.raises(EngineRunFailed):
        run_for_service(biz, {"financials": None})


@pytest.mark.parametrize("garbage", [None, {}, [], "x", {"status": "completed"}, {"status": "completed", "metrics": 5}])
def test_to_api_result_never_raises(garbage):
    api = to_api_result(garbage)
    assert api["status"] == "failed" and api["error_message"] and api["evidence_level"] == "insufficient"


# ---------------- drift guard: JSON schema and Pydantic model must agree ------------------------------------
def _mut(fn):
    def apply(d):
        fn(d)
        return d
    return apply


MUTATIONS = {
    "bad status": (_mut(lambda d: d.update(status="done")), False),
    "bad evidence level": (_mut(lambda d: d.update(evidence_level="great")), False),
    "bad benchmark status": (_mut(lambda d: d.update(benchmark_status="maybe")), False),
    "missing core field": (_mut(lambda d: d.pop("metrics")), False),
    "non-numeric metric": (_mut(lambda d: d["metrics"].update(revenue="abc")), False),
    "bad finding severity": (_mut(lambda d: d["findings"][0].update(severity="high")), False),
    "bad finding category": (_mut(lambda d: d["findings"][0].update(category="other")), False),
    "finding missing title": (_mut(lambda d: d["findings"][0].pop("title")), False),
    "bad priority": (_mut(lambda d: d["recommendations"][0].update(priority="urgent")), False),
    "recommendation without findings": (_mut(lambda d: d["recommendations"][0].update(supporting_finding_ids=[])), False),
    "bad expected_direction": (_mut(lambda d: d["recommendations"][0].update(expected_direction="up")), False),
    "failed without message": (_mut(lambda d: d.update(status="failed", error_message=None)), False),
    "pending is valid": (_mut(lambda d: d.update(status="pending")), True),
    "insufficient evidence is valid": (_mut(lambda d: d.update(evidence_level="insufficient")), True),
    "failed with message is valid": (_mut(lambda d: d.update(status="failed", error_message="No data.")), True),
    "null metric is valid": (_mut(lambda d: d["metrics"].update(profit=None)), True),
    "maintain direction is valid": (_mut(lambda d: d["recommendations"][0].update(expected_direction="maintain")), True),
}


@pytest.mark.parametrize("name", list(MUTATIONS))
def test_json_schema_and_pydantic_agree(validator, name):
    mutate, expected_valid = MUTATIONS[name]
    d = mutate(copy.deepcopy(to_api_result(native("retail"))))
    schema_ok = not list(validator.iter_errors(d))
    assert schema_ok == expected_valid, f"JSON schema: {name}"
    assert pydantic_ok(d) == expected_valid, f"Pydantic: {name}"
