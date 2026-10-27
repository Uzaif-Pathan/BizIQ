import json

import pytest

from conftest import SAMPLES
from analytics_engine.scoring import BASE_WEIGHTS, compute_health_score, curve
from analytics_engine.scoring import health_score as hs


def res(**metrics):
    return {"metrics": {k: {"value": v} for k, v in metrics.items()}, "monthly": [], "trend": {}}


def comp(h, name):
    return next(c for c in h["components"] if c["name"] == name)


FIN_FULL = res(profit_margin_pct=20.0, revenue_12m_growth_pct=10.0, expenses_yoy_pct=5.0, revenue_yoy_pct=10.0)


# ---------------- curves -------------------------------------------------------------
def test_base_weights_sum_to_100():
    assert sum(BASE_WEIGHTS.values()) == 100


@pytest.mark.parametrize("name,x,expected", [
    ("margin", 20, 85), ("margin", 12.5, 70.0), ("margin", -50, 0), ("margin", 99, 100),
    ("growth", 0, 50), ("growth", 5, 60), ("cost_gap_pp", 0, 65), ("cost_gap_pp", -2.5, 75),
    ("top_customer_share", 10, 85), ("top_product_share", 25, 100), ("top_product_share", 90, 0),
])
def test_curve_values_by_hand(name, x, expected):
    assert curve(name, x) == pytest.approx(expected)


@pytest.mark.parametrize("name", list(hs.CURVES))
def test_every_curve_is_in_range_and_monotonic_in_one_direction(name):
    xs = [p[0] for p in hs.CURVES[name]]
    ys = [curve(name, x) for x in range(int(xs[0]) - 5, int(xs[-1]) + 6)]
    assert all(0 <= y <= 100 for y in ys)
    diffs = [b - a for a, b in zip(ys, ys[1:])]
    assert all(d >= -1e-9 for d in diffs) or all(d <= 1e-9 for d in diffs)


# ---------------- components -----------------------------------------------------------
def test_profitability_measured_when_no_benchmark():
    c = comp(compute_health_score(FIN_FULL), "profitability")
    assert c["basis"] == "measured" and c["points"] == 85.0 and c["value"] == 20.0


def test_profitability_uses_matching_benchmark_and_records_its_source():
    bm = [{"metric": "profit_margin_pct", "value": 15.0, "source": "Survey X", "year": 2024,
           "geography": "Maharashtra", "geography_level": "state", "definition": "net margin"}]
    c = comp(compute_health_score(FIN_FULL, benchmarks=bm), "profitability")
    assert c["basis"] == "benchmark"
    assert c["points"] == pytest.approx(curve("margin_vs_benchmark_pp", 5.0), abs=0.1)  # 20% vs 15%
    assert c["benchmark"]["source"] == "Survey X" and c["benchmark"]["geography_level"] == "state"
    assert "Survey X" in c["explanation"]


def test_mismatched_or_malformed_benchmarks_are_ignored():
    bad = [{"metric": "gross_margin_pct", "value": 40}, {"metric": "profit_margin_pct", "value": "abc"},
           {"metric": "profit_margin_pct", "value": float("nan")}, "junk", None]
    c = comp(compute_health_score(FIN_FULL, benchmarks=bad), "profitability")
    assert c["basis"] == "measured"


def test_profit_unavailable_means_no_profitability_component():
    fin = res(revenue_12m_growth_pct=10.0, profit_margin_pct=None)
    h = compute_health_score(fin)
    assert "profitability" in h["unavailable_components"]
    assert any("profit margin unavailable" in l for l in h["limitations"])


def test_growth_prefers_12m_then_yoy_then_clear_trend_only():
    assert comp(compute_health_score(res(revenue_12m_growth_pct=10, revenue_yoy_pct=-30, profit_margin_pct=10)), "growth")["value"] == 10
    assert comp(compute_health_score(res(revenue_yoy_pct=-30, profit_margin_pct=10)), "growth")["value"] == -30
    fin = {"metrics": {"profit_margin_pct": {"value": 10}}, "monthly": [],
           "trend": {"revenue": {"pct_per_month": 1.0, "direction": "increasing"}}}
    assert comp(compute_health_score(fin), "growth")["value"] == 12.0  # annualised
    fin["trend"]["revenue"]["direction"] = "unclear"
    assert "growth" in compute_health_score(fin)["unavailable_components"]


def test_cost_control_compares_expense_growth_with_revenue_growth():
    c = comp(compute_health_score(res(expenses_yoy_pct=15, revenue_yoy_pct=5, profit_margin_pct=10)), "cost_control")
    assert c["value"] == 10 and c["points"] == 20.0


def test_stability_needs_six_months_and_uses_cv():
    fin = {"metrics": {}, "trend": {}, "monthly": [{"revenue": v} for v in (90, 100, 110, 90, 100, 110)]}
    fin["metrics"] = {"profit_margin_pct": {"value": 10}}
    c = comp(compute_health_score(fin), "revenue_stability")
    assert c["basis"] == "rule" and c["value"] == pytest.approx(8.94, abs=0.01) and c["points"] == 100.0
    fin["monthly"] = fin["monthly"][:5]
    assert "revenue_stability" in compute_health_score(fin)["unavailable_components"]


def test_customer_components_and_small_customer_base():
    cus = res(repeat_customer_rate_pct=50, avg_monthly_retention_pct=40, active_customers=100,
              top_customer_share_pct=15, top_10pct_customers_share_pct=50)
    h = compute_health_score(FIN_FULL, cus)
    assert comp(h, "customer_loyalty")["points"] == pytest.approx((75 + 60) / 2)
    assert comp(h, "customer_concentration")["points"] == 70.0  # min(70, 70)
    cus["metrics"]["active_customers"]["value"] = 4
    assert "customer_concentration" in compute_health_score(FIN_FULL, cus)["unavailable_components"]


def test_product_margin_penalises_loss_making_products_and_concentration_needs_3_products():
    pro = res(gross_margin_pct=35, products_with_negative_margin=2, product_count=2, top_product_share_pct=70)
    h = compute_health_score(FIN_FULL, None, pro)
    assert comp(h, "product_margin")["points"] == 65.0  # 85 - 20
    assert "product_concentration" in h["unavailable_components"]


# ---------------- scoring, weights, guards ------------------------------------------------
def test_weights_renormalise_and_score_is_weighted_average():
    h = compute_health_score(FIN_FULL)
    assert sum(c["weight"] for c in h["components"]) == pytest.approx(100, abs=0.2)
    expected = sum(c["weight"] * c["points"] for c in h["components"]) / 100
    assert h["score"] == pytest.approx(expected, abs=0.15)
    assert h["coverage_pct"] == 60 and any("redistributed" in l for l in h["limitations"])


def test_score_equals_50_plus_sum_of_effect_points():
    cus = res(repeat_customer_rate_pct=30, avg_monthly_retention_pct=30, active_customers=50,
              top_customer_share_pct=30, top_10pct_customers_share_pct=60)
    h = compute_health_score(FIN_FULL, cus)
    assert h["score"] == pytest.approx(50 + sum(c["effect_points"] for c in h["components"]), abs=0.3)


def test_directions_and_raised_lowered_lists():
    fin = res(profit_margin_pct=30.0, revenue_12m_growth_pct=-20.0)
    h = compute_health_score(fin)
    assert comp(h, "profitability")["direction"] == "raises" and comp(h, "growth")["direction"] == "lowers"
    assert h["raised_by"] == ["profitability"] and h["lowered_by"] == ["growth"]
    assert h["components"][0]["name"] in ("profitability", "growth")  # biggest effect first


def test_no_score_without_a_financial_outcome_even_with_lots_of_customer_data():
    cus = res(repeat_customer_rate_pct=80, avg_monthly_retention_pct=80, active_customers=100,
              top_customer_share_pct=3, top_10pct_customers_share_pct=20)
    pro = res(gross_margin_pct=50, products_with_negative_margin=0, product_count=9, top_product_share_pct=10)
    steady = {"metrics": {}, "trend": {}, "monthly": [{"revenue": v} for v in (100, 101, 99, 100, 102, 98)]}
    h = compute_health_score(steady, cus, pro)  # stability + customers + products = exactly 40 % weight
    assert h["coverage_pct"] == 40
    assert h["score"] is None and h["band"] is None and "Not enough data" in h["limitations"][0]
    assert all(c["weight"] is None for c in h["components"])  # shown, but not weighted


def test_no_score_when_available_weight_below_40():
    h = compute_health_score(res(revenue_yoy_pct=5.0))  # growth only = 20 %
    assert h["score"] is None and h["coverage_pct"] == 20


def test_nothing_available_gives_null_score_and_all_unavailable():
    for args in ((None, None, None), ({}, {}, {}), ({"available": False, "metrics": {}}, None, None)):
        h = compute_health_score(*args)
        assert h["score"] is None and set(h["unavailable_components"]) == set(BASE_WEIGHTS)


def test_band_thresholds():
    assert [hs._band(s) for s in (80, 60, 40, 10)] == ["strong", "moderate", "weak", "at risk"]


def test_always_carries_the_not_a_probability_disclaimer():
    for h in (compute_health_score(FIN_FULL), compute_health_score(None)):
        assert "not a probability" in h["disclaimer"]


def test_garbage_input_never_raises():
    h = compute_health_score({"metrics": "oops"}, 5, [1, 2])
    assert h["score"] is None and h["limitations"]


def test_deterministic_and_strict_json():
    cus = res(repeat_customer_rate_pct=30, active_customers=50, top_customer_share_pct=30)
    a, b = compute_health_score(FIN_FULL, cus), compute_health_score(FIN_FULL, cus)
    assert a == b
    json.dumps(a, allow_nan=False)


# ---------------- real pipeline on the sample datasets ----------------------------------------
def _analyse(scenario):
    import pandas as pd
    import analytics_engine.customers as C, analytics_engine.financial as F, analytics_engine.products as P
    from analytics_engine.validation import validate_table

    def load(t):
        p = SAMPLES / scenario / f"{t}.csv"
        return validate_table(pd.read_csv(p), t).clean if p.exists() else None
    return (F.analyze_financials(load("financials")), C.analyze_customers(load("customers")),
            P.analyze_products(load("products")))


def test_retail_sample_scores_with_all_components():
    h = compute_health_score(*_analyse("retail"))
    assert h["score"] is not None and 0 <= h["score"] <= 100 and h["unavailable_components"] == []


@pytest.mark.parametrize("scenario", ["service", "cold_start", "messy"])
def test_limited_data_samples_get_no_score_and_say_why(scenario):
    h = compute_health_score(*_analyse(scenario))
    assert h["score"] is None and h["limitations"]


def test_health_score_matches_contract_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SAMPLES.parents[1] / "contracts" / "engine-result.schema.json").read_text())
    ref = {"$ref": "#/properties/health_score", "$defs": schema["$defs"], "properties": schema["properties"]}
    for scenario in ("retail", "service", "cold_start"):
        jsonschema.validate(compute_health_score(*_analyse(scenario)), ref)
