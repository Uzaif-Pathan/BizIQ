import json

import pytest

from conftest import SAMPLES

SCHEMA_PATH = SAMPLES.parents[1] / "contracts" / "engine-result.schema.json"


def test_schema_is_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text()))


def test_metric_definition_accepts_trend_extras_and_rejects_missing_value():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text())
    ref = {"$ref": "#/$defs/metric", "$defs": schema["$defs"]}
    jsonschema.validate({"value": 1.5, "unit": "percent_per_month", "period": "2025-01/2025-06",
                         "formula": "x", "direction": "increasing", "r_squared": 0.9,
                         "months_used": 6, "note": None}, ref)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"unit": "INR"}, ref)


# ---- the engine schema must actually reject wrong output (guards against a vacuous schema) ----
def _good_result():
    import pandas as pd
    from analytics_engine import run_analysis
    biz = json.loads((SAMPLES / "businesses.json").read_text())["retail"]
    data = {t: pd.read_csv(SAMPLES / "retail" / f"{t}.csv") for t in ("financials", "customers", "products")}
    return run_analysis(biz, data)


@pytest.fixture(scope="module")
def validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))


def test_good_engine_output_validates(validator):
    assert list(validator.iter_errors(_good_result())) == []


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r.update(unexpected_field=1), "unknown top-level field (drift)"),
    (lambda r: r.update(status="done"), "bad status"),
    (lambda r: r.update(evidence_level="insufficient"), "engine evidence levels are low/medium/high"),
    (lambda r: r["findings"][0].update(severity="critical"), "bad finding severity"),
    (lambda r: r["findings"][0].pop("evidence"), "finding without evidence"),
    (lambda r: r["recommendations"][0].update(finding_ids=[]) if r["recommendations"]
        else r["recommendations"].append({"id": "R", "finding_ids": [], "issue": "i", "action": "a",
                                          "priority": "high", "evidence": "e"}), "recommendation without findings"),
    (lambda r: r["metrics"].update(revenue=12), "metric must be an object, not a bare number"),
    (lambda r: r["metrics"]["revenue"].pop("value"), "metric without value"),
])
def test_schema_rejects_wrong_output(validator, mutate, why):
    r = _good_result()
    mutate(r)
    assert list(validator.iter_errors(r)), why
