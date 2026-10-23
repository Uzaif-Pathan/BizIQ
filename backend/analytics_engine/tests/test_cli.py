import json
from pathlib import Path

from analytics_engine.cli import _load_scenario, _validate_schema
from analytics_engine.pipeline import run_analysis

ROOT = Path(__file__).resolve().parents[3]


def test_all_sample_scenarios_load():
    samples = ROOT / "data" / "samples"
    for name in ("retail", "service", "cold_start", "messy"):
        business, data = _load_scenario(samples, name)
        assert business["business_id"]
        assert data
        assert "financials" in data


def test_retail_pipeline_result_matches_schema():
    samples = ROOT / "data" / "samples"
    business, data = _load_scenario(samples, "retail")
    result = run_analysis(business, data)
    errors = _validate_schema(result, ROOT / "contracts" / "analysis-result.schema.json")
    assert errors == [], "\\n".join(errors)
    # Ensure the result is actually JSON serializable without NaN/Infinity.
    json.dumps(result, allow_nan=False)


def test_unknown_scenario_is_rejected():
    samples = ROOT / "data" / "samples"
    try:
        _load_scenario(samples, "does-not-exist")
    except ValueError as exc:
        assert "Unknown scenario" in str(exc)
    else:
        raise AssertionError("Unknown scenarios should raise ValueError")



def test_cli_main_writes_schema_valid_json(tmp_path):
    from analytics_engine.cli import main

    target = tmp_path / "result.json"
    code = main([
        "--scenario", "cold_start",
        "--output", str(target),
        "--check-schema",
    ])
    assert code == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["business_id"]
    assert result["status"] in {"completed", "partial"}



def test_summary_is_readable_and_handles_missing_metrics():
    from analytics_engine.cli import _render_summary

    text = _render_summary({
        "status": "partial",
        "evidence_level": "low",
        "benchmark_status": "unavailable",
        "metrics": {"profit": {"value": None, "unit": "INR"}},
        "health_score": None,
        "findings": [],
        "recommendations": [],
        "models": {},
        "validation": {"errors": [], "warnings": []},
    }, {"name": "Sample Business"})
    assert "Sample Business" in text
    assert "Score unavailable" in text
    assert "No supported findings" in text
    assert "Data quality: 0 error(s), 0 warning(s)" in text
