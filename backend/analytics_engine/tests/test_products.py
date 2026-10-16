"""Product analytics tests with hand-computed expectations."""

import json

import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.products import analyze_products, build_product_findings
from analytics_engine.validation import validate_table

COLS = ("period", "product_id", "product_name", "units_sold", "revenue", "cost")


def run(rows, rev=None, window=None, cols=COLS):
    rep = validate_table(pd.DataFrame(rows, columns=list(cols)), "products")
    return analyze_products(rep.clean, rev, window)


def val(res, key):
    return res["metrics"][key]["value"]


def prod(res, pid):
    return next(p for p in res["products"] if p["product_id"] == pid)


def months(n, year=2025):
    return [f"{year}-{i + 1:02d}" for i in range(n)]


# P1 earns, P2 loses money; 3 months each
TWO = [(m, "P1", "Alpha", 10, 100, 80) for m in months(3)] + \
      [(m, "P2", "Beta", 5, 50, 60) for m in months(3)]


def test_per_product_numbers():
    r = run(TWO)
    p1, p2 = prod(r, "P1"), prod(r, "P2")
    assert (p1["revenue"], p1["cost"], p1["gross_profit"], p1["gross_margin_pct"]) == (300, 240, 60, 20.0)
    assert (p2["revenue"], p2["cost"], p2["gross_profit"], p2["gross_margin_pct"]) == (150, 180, -30, -20.0)
    assert p1["units_sold"] == 30 and p1["revenue_share_pct"] == pytest.approx(66.67, abs=0.01)
    assert p1["rank_by_revenue"] == 1 and p2["rank_by_revenue"] == 2
    assert p1["rank_by_gross_profit"] == 1 and p2["rank_by_gross_profit"] == 2


def test_overall_metrics():
    r = run(TWO)
    assert val(r, "product_count") == 2 and val(r, "total_product_revenue") == 450
    assert val(r, "gross_profit") == 30 and val(r, "gross_margin_pct") == pytest.approx(6.67, abs=0.01)
    assert val(r, "products_with_negative_margin") == 1
    assert val(r, "top_product_share_pct") == pytest.approx(66.67, abs=0.01)
    assert val(r, "top_3_products_share_pct") is None  # needs more than 3 products


def test_partial_cost_blocks_margin_instead_of_overstating_it():
    rows = [("2025-01", "P1", "Alpha", 1, 100, 80), ("2025-02", "P1", "Alpha", 1, 100, None),
            ("2025-01", "P2", "Beta", 1, 50, 20), ("2025-02", "P2", "Beta", 1, 50, 20)]
    r = run(rows)
    p1 = prod(r, "P1")
    assert p1["cost"] is None and p1["gross_margin_pct"] is None and "cost missing" in p1["cost_note"]
    assert prod(r, "P2")["gross_margin_pct"] == 60.0
    assert val(r, "gross_margin_pct") is None and "missing" in r["metrics"]["gross_margin_pct"]["reason"]
    assert val(r, "products_with_negative_margin") == 0
    assert "1 of 2" in r["metrics"]["products_with_negative_margin"]["note"]


def test_no_cost_column_means_no_margin_at_all():
    r = run([("2025-01", "P1", "A", 1, 100), ("2025-01", "P2", "B", 1, 50)],
            cols=("period", "product_id", "product_name", "units_sold", "revenue"))
    assert val(r, "gross_margin_pct") is None and val(r, "products_with_negative_margin") is None
    assert prod(r, "P1")["rank_by_gross_profit"] is None


def test_missing_units_stay_missing_and_name_falls_back_to_id():
    r = run([("2025-01", "P1", None, None, 100, 50), ("2025-01", "P2", "B", 4, 50, 20)])
    assert prod(r, "P1")["units_sold"] is None and prod(r, "P1")["product_name"] == "P1"
    assert prod(r, "P2")["units_sold"] == 4


def test_single_product_cannot_be_ranked():
    r = run([("2025-01", "P1", "A", 1, 100, 50)])
    assert r["available"] and val(r, "top_product_share_pct") is None
    assert r["top_performers"] == [] and r["low_performers"] == []
    assert build_product_findings(r) == []


def test_top_and_low_performers_do_not_overlap():
    rows = [("2025-01", f"P{i}", f"N{i}", 1, 100 - 10 * i, 10) for i in range(5)]  # 100,90,80,70,60
    r = run(rows)
    assert r["top_performers"] == ["P0", "P1"] and r["low_performers"] == ["P4", "P3"]  # n//2 = 2 each
    assert val(r, "top_3_products_share_pct") == pytest.approx(270 / 400 * 100)


def test_share_and_revenue_trends():
    ms = months(8)
    rows = []
    for i, m in enumerate(ms):
        rows.append((m, "UP", "Rising", 1, 100 + 10 * i, 10))
        rows.append((m, "FLAT", "Steady", 1, 500, 10))
        rows.append((m, "DOWN", "Falling", 1, 300 - 20 * i, 10))  # total shrinks 10/month
    r = run(rows)
    assert prod(r, "UP")["revenue_trend"]["direction"] == "increasing"
    assert prod(r, "UP")["share_trend"]["direction"] == "increasing"
    assert prod(r, "FLAT")["revenue_trend"]["direction"] == "flat"
    assert prod(r, "FLAT")["share_trend"]["direction"] == "increasing"  # flat revenue, shrinking total
    assert prod(r, "DOWN")["revenue_trend"]["direction"] == "decreasing"


def test_absent_month_is_missing_not_zero_in_trend():
    rows = [(m, "P1", "A", 1, 100, 10) for m in months(8) if m != "2025-04"]
    p = prod(run(rows), "P1")
    assert p["months_active"] == 7
    assert p["revenue_trend"]["n_points"] == 7 and p["revenue_trend"]["direction"] == "flat"


def test_only_latest_12_months_counted():
    rows = [("2024-01", "P1", "A", 1, 999, 1)] + [(m, "P1", "A", 1, 10, 5) for m in
                                                    [f"2025-{i:02d}" for i in range(1, 13)]]
    r = run(rows)
    assert prod(r, "P1")["revenue"] == 120 and r["coverage"]["months"] == 12


def test_coverage_against_financial_revenue():
    r = run(TWO, rev=900, window=("2025-01", "2025-03"))
    assert val(r, "product_data_coverage_pct") == 50.0
    assert val(run(TWO), "product_data_coverage_pct") is None


def test_unavailable_when_no_data():
    for clean in (None, pd.DataFrame()):
        r = analyze_products(clean)
        assert r["available"] is False and r["reason"] and r["products"] == []
        assert build_product_findings(r) == []


# ---------- findings --------------------------------------------------------------------
def f(res):
    return {x["id"]: x for x in build_product_findings(res)}


def test_concentration_and_negative_margin_findings():
    found = f(run(TWO))
    assert found["PRD-CONC"]["severity"] == "high"  # 66.7% >= 60
    assert found["PRD-NEGMARGIN-P2"]["severity"] == "high"
    assert "costs more than it earns" in found["PRD-NEGMARGIN-P2"]["evidence"]


def test_low_margin_main_product_finding():
    rows = [("2025-01", "BIG", "Big", 1, 600, 570), ("2025-01", "S1", "Small", 1, 400, 100)]  # 5% margin, 60% share
    found = f(run(rows))
    assert found["PRD-LOWMARGIN-BIG"]["severity"] == "medium"
    assert "PRD-LOWMARGIN-S1" not in found


def test_decline_and_gaining_findings():
    ms = months(8)
    rows = []
    for i, m in enumerate(ms):
        rows.append((m, "UP", "Rising", 1, 200 + 25 * i, 10))
        rows.append((m, "DOWN", "Falling", 1, 400 - 25 * i, 10))
    found = f(run(rows))
    assert found["PRD-DECLINE-DOWN"]["type"] == "product_revenue_declining"
    assert found["PRD-DECLINE-DOWN"]["severity"] == "medium"  # large share
    assert "PRD-DECLINE-UP" not in found


def test_low_contribution_finding_needs_five_products():
    big = [("2025-01", "A", "A", 1, 500, 10), ("2025-01", "B", "B", 1, 400, 10)]
    tiny = [("2025-01", f"T{i}", f"T{i}", 1, 10, 5) for i in range(3)]  # 3.3%... each under 5%
    assert "PRD-LOWCONTRIB" in f(run(big + tiny))
    assert "PRD-LOWCONTRIB" not in f(run(big + tiny[:2]))  # only 4 products


def test_low_coverage_finding():
    assert f(run(TWO, rev=100000, window=("2025-01", "2025-03")))["PRD-COVERAGE"]["value"] == 0.45


# ---------- samples -------------------------------------------------------------------------
def test_retail_sample_strict_json_and_independent_sums():
    df = pd.read_csv(SAMPLES / "retail" / "products.csv")
    res = analyze_products(validate_table(df, "products").clean)
    json.dumps(res, allow_nan=False)
    json.dumps(build_product_findings(res), allow_nan=False)
    d25 = df[df.period.str.startswith("2025")]
    assert val(res, "total_product_revenue") == pytest.approx(d25.revenue.sum(), abs=0.01)
    p01 = d25[d25.product_id == "P01"]
    assert prod(res, "P01")["gross_profit"] == pytest.approx(p01.revenue.sum() - p01.cost.sum(), abs=0.01)
    assert res["products"][0]["product_id"] == d25.groupby("product_id").revenue.sum().idxmax()
