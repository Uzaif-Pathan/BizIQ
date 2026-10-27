import json

import numpy as np
import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.ml import forecast_revenue
from analytics_engine.ml import forecast as fc
from analytics_engine.validation import validate_table


def series(values, start="2024-01"):
    periods = pd.period_range(start, periods=len(values), freq="M").astype(str)
    df = pd.DataFrame({"period": periods, "revenue": values, "expenses": 1.0, "expenses_complete": True})
    return validate_table(df, "financials").clean


def test_perfect_linear_growth_picks_linear_with_zero_error_and_exact_forecast():
    m = forecast_revenue(series([1000 + 100 * i for i in range(12)]))  # 1000 .. 2100
    d = m["details"]
    assert m["status"] == "ok" and d["model_name"] == "linear" and d["beats_naive"] is True
    assert m["mae"] == pytest.approx(0, abs=0.01) and m["rmse"] == pytest.approx(0, abs=0.01)
    assert [f["value"] for f in d["forecast"]] == [2200, 2300, 2400]
    assert [f["period"] for f in d["forecast"]] == ["2025-01", "2025-02", "2025-03"]
    assert d["train_months"] == 9 and d["holdout_months"] == 3


def test_constant_series_prefers_the_simplest_model_and_flags_no_trend():
    m = forecast_revenue(series([5000.0] * 12))
    d = m["details"]
    assert m["status"] == "ok" and d["model_name"] == "naive" and d["beats_naive"] is False
    assert d["caveat"] and all(f["value"] == 5000 for f in d["forecast"])


def test_holdout_scores_are_computed_by_hand():
    # train 6 months of 100, holdout 120, 100, 80 -> naive/ma3 predict 100 -> errors 20,0,20
    m = forecast_revenue(series([100] * 6 + [120, 100, 80]))
    naive = next(c for c in m["details"]["candidates"] if c["name"] == "naive")
    assert naive["mae"] == pytest.approx(40 / 3, abs=0.01)
    assert naive["rmse"] == pytest.approx(np.sqrt((400 + 0 + 400) / 3), abs=0.01)
    assert naive["mape_pct"] == pytest.approx((20 / 120 + 0 + 20 / 80) / 3 * 100, abs=0.01)


def test_too_few_months_skipped_with_reason_and_no_numbers():
    m = forecast_revenue(series([100] * 8))
    assert m["status"] == "skipped_insufficient_data" and m["details"]["skip_code"] == "too_few_months"
    assert "9" in m["details"]["reason"] and m["mae"] is None and "forecast" not in m["details"]


def test_none_and_empty_not_applicable():
    assert forecast_revenue(None)["status"] == "not_applicable"
    assert forecast_revenue(pd.DataFrame())["status"] == "not_applicable"


def test_erratic_series_is_withheld_instead_of_shown_as_reliable():
    vals = [100, 900, 150, 800, 120, 950, 100, 900, 130, 880, 90, 1000]
    m = forecast_revenue(series(vals))
    assert m["status"] == "skipped_insufficient_data" and m["details"]["skip_code"] == "poor_accuracy"
    assert "forecast" not in m["details"]
    assert m["mae"] is not None and m["details"]["candidates"]  # evaluation is still reported


def test_missing_revenue_months_are_not_zero_filled():
    vals = [1000 + 100 * i for i in range(13)]
    df = series(vals)
    df.loc[df["period"] == "2024-04", "revenue"] = np.nan
    m = forecast_revenue(df)
    assert m["details"]["months_with_revenue"] == 12  # the NaN month is ignored, not a 0


def test_calendar_gap_is_respected_in_the_fit():
    # months 2024-01..2024-05, skip 06, then 07..2024-12; value = 1000 + 100 * calendar month index
    idx = [i for i in range(12) if i != 5]
    df = pd.DataFrame({"period": [str(pd.Period("2024-01") + i) for i in idx],
                       "revenue": [1000.0 + 100 * i for i in idx], "expenses": 1.0, "expenses_complete": True})
    m = forecast_revenue(validate_table(df, "financials").clean)
    assert m["status"] == "ok" and m["details"]["model_name"] == "linear"
    assert m["details"]["forecast"][0]["value"] == 2200  # month index 12


def test_forecast_crosses_year_boundary_and_horizon_is_capped():
    m = forecast_revenue(series([1000 + 100 * i for i in range(11)], start="2024-02"), horizon=99)
    d = m["details"]
    assert d["horizon_months"] == 6 and d["forecast"][0]["period"] == "2025-01"
    assert d["forecast"][-1]["period"] == "2025-06"


def test_band_is_clamped_at_zero_and_ordered():
    m = forecast_revenue(series([100 + 10 * i + (5 if i % 2 else -5) for i in range(12)]))
    for f in m["details"]["forecast"]:
        assert 0 <= f["low"] <= f["value"] <= f["high"]


def test_non_positive_revenue_skipped():
    assert forecast_revenue(series([0.0] * 12))["details"]["skip_code"] == "non_positive_revenue"


def test_deterministic_json_safe_and_input_unchanged():
    df = series([1000 + 100 * i for i in range(12)])
    before = df.copy()
    a, b = forecast_revenue(df), forecast_revenue(df)
    assert a == b
    pd.testing.assert_frame_equal(df, before)
    json.dumps(a, allow_nan=False)


def test_never_raises_on_garbage():
    bad = pd.DataFrame({"period": ["x", "y"], "revenue": ["a", "b"]})
    assert forecast_revenue(bad)["status"] in ("failed", "skipped_insufficient_data", "not_applicable")


@pytest.mark.parametrize("scenario,status", [("retail", "ok"), ("service", "ok"),
                                              ("cold_start", "skipped_insufficient_data"),
                                              ("messy", "skipped_insufficient_data")])
def test_sample_datasets(scenario, status):
    c = validate_table(pd.read_csv(SAMPLES / scenario / "financials.csv"), "financials").clean
    m = forecast_revenue(c)
    assert m["status"] == status
    if status == "ok":
        assert m["details"]["mape_pct"] <= fc.MAX_MAPE_PCT and len(m["details"]["forecast"]) == 3


def test_model_object_matches_contract_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SAMPLES.parents[1] / "contracts" / "engine-result.schema.json").read_text())
    ref = {"$ref": "#/$defs/model", "$defs": schema["$defs"]}
    for m in (forecast_revenue(series([1000 + 100 * i for i in range(12)])), forecast_revenue(None),
              forecast_revenue(series([100] * 5))):
        jsonschema.validate(m, ref)
