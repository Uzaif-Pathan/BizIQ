"""Tests for financial metrics and findings. Expected values are worked out by hand."""

import json

import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.financial import analyze_financials, build_financial_findings
from analytics_engine.validation import validate_table


def run(rows, cols=("period", "revenue", "expenses", "expenses_complete")):
    rep = validate_table(pd.DataFrame(rows, columns=list(cols)), "financials")
    return analyze_financials(rep.clean)


def val(res, key):
    return res["metrics"][key]["value"]


def months(start_year, n, start_month=1):
    return [f"{start_year + (start_month - 1 + i) // 12}-{(start_month - 1 + i) % 12 + 1:02d}"
            for i in range(n)]


# ---------- totals, profit, margin --------------------------------------------
def test_complete_expenses_give_profit_margin_and_ratio():
    r = run([("2025-01", 100, 80, True), ("2025-02", 200, 150, True), ("2025-03", 300, 240, True)])
    assert val(r, "revenue") == 600
    assert val(r, "expenses") == 470 and val(r, "listed_expenses") == 470
    assert val(r, "profit") == 130
    assert val(r, "profit_margin_pct") == pytest.approx(21.67, abs=0.01)  # 130/600
    assert val(r, "expense_ratio_pct") == pytest.approx(78.33, abs=0.01)  # 470/600
    assert r["metrics"]["revenue"]["period"] == "2025-01/2025-03"


def test_incomplete_expense_list_blocks_profit_but_keeps_listed_numbers():
    r = run([("2025-01", 100, 80, False), ("2025-02", 200, 150, False)])
    for k in ("expenses", "profit", "profit_margin_pct", "expense_ratio_pct"):
        assert val(r, k) is None
        assert "incomplete" in r["metrics"][k]["reason"]
    assert val(r, "listed_expenses") == 230
    assert val(r, "revenue_minus_listed_expenses") == 70  # 300 - 230


def test_unknown_expense_definition_is_not_assumed_complete():
    r = run([("2025-01", 100, 80), ("2025-02", 200, 150)], cols=("period", "revenue", "expenses"))
    assert val(r, "profit") is None
    assert "unknown" in r["metrics"]["profit"]["reason"]


def test_one_incomplete_month_makes_whole_window_incomplete():
    r = run([("2025-01", 100, 80, True), ("2025-02", 200, 150, False)])
    assert val(r, "profit") is None


def test_profit_needs_expenses_for_every_revenue_month():
    r = run([("2025-01", 100, 80, True), ("2025-02", 200, None, True)])
    assert val(r, "profit") is None
    assert "missing" in r["metrics"]["profit"]["reason"]
    assert val(r, "revenue") == 300  # revenue still counted
    assert val(r, "revenue_minus_listed_expenses") == 20  # only the month having both


def test_no_expense_column_values_at_all():
    r = run([("2025-01", 100, None, None), ("2025-02", 200, None, None)])
    assert val(r, "listed_expenses") is None and val(r, "expenses") is None
    assert val(r, "revenue") == 300 and val(r, "profit") is None


def test_margin_is_null_when_revenue_is_zero():
    r = run([("2025-01", 0, 50, True), ("2025-02", 0, 60, True)])
    assert val(r, "profit") == -110
    assert val(r, "profit_margin_pct") is None
    assert "not positive" in r["metrics"]["profit_margin_pct"]["reason"]


def test_missing_revenue_month_is_not_counted_as_zero_and_is_disclosed():
    r = run([("2025-01", 100, 80, True), ("2025-02", None, 80, True), ("2025-03", 300, 90, True)])
    assert val(r, "revenue") == 400
    assert "2 of 3" in r["metrics"]["revenue"]["note"]
    assert val(r, "months_of_data") == 2
    assert [m["revenue"] for m in r["monthly"]] == [100, None, 300]  # None, never 0


def test_loss_is_a_valid_negative_profit():
    r = run([("2025-01", 100, 130, True), ("2025-02", 100, 120, True)])
    assert val(r, "profit") == -50 and val(r, "profit_margin_pct") == -25


def test_empty_and_none_input():
    for clean in (None, pd.DataFrame()):
        r = analyze_financials(clean)
        assert r["metrics"] == {} and r["coverage"]["months_with_revenue"] == 0
        assert build_financial_findings(r) == []


# ---------- reporting window ------------------------------------------------------
def test_window_is_latest_12_months_only():
    ms = months(2024, 14)  # 2024-01 .. 2025-02
    r = run([(m, 100, 70, True) for m in ms])
    assert r["coverage"]["window_first"] == "2024-03" and r["coverage"]["window_last"] == "2025-02"
    assert val(r, "revenue") == 1200  # 12 months, not 14
    assert r["coverage"]["months_with_revenue"] == 14


# ---------- MoM / YoY -------------------------------------------------------------------
def test_mom_and_yoy_from_calendar_neighbours():
    ms = months(2024, 13)
    rev = [100] * 12 + [150]
    r = run([(m, v, 50, True) for m, v in zip(ms, rev)])
    assert val(r, "revenue_mom_pct") == pytest.approx(50.0)  # 150 vs 100
    assert val(r, "revenue_yoy_pct") == pytest.approx(50.0)  # 2025-01 vs 2024-01
    assert val(r, "expenses_mom_pct") == pytest.approx(0.0)


def test_mom_is_null_across_a_calendar_gap_not_shifted():
    r = run([("2025-01", 100, 50, True), ("2025-03", 200, 60, True)])
    assert val(r, "revenue_mom_pct") is None  # 2025-02 absent; January must not be used
    assert "no valid revenue" in r["metrics"]["revenue_mom_pct"]["reason"]


def test_change_from_zero_or_negative_base_is_null():
    r = run([("2025-01", 0, 50, True), ("2025-02", 100, 60, True)])
    assert val(r, "revenue_mom_pct") is None
    r = run([("2025-01", -50, 50, True), ("2025-02", 100, 60, True)])
    assert val(r, "revenue_mom_pct") is None


def test_expense_changes_need_complete_list():
    r = run([("2025-01", 100, 50, False), ("2025-02", 100, 60, False)])
    assert val(r, "expenses_mom_pct") is None
    r = run([("2025-01", 100, 50, True), ("2025-02", 100, 60, True)])
    assert val(r, "expenses_mom_pct") == pytest.approx(20.0)


def test_yoy_absent_when_no_year_ago_month():
    r = run([(m, 100, 60, True) for m in months(2025, 6)])
    assert val(r, "revenue_yoy_pct") is None


def test_comparison_touching_flagged_month_carries_a_note():
    rows = [(m, 100, 60, True) for m in months(2025, 7)] + [("2025-08", 5000, 60, True)]
    r = run(rows)
    assert val(r, "revenue_mom_pct") == pytest.approx(4900.0)
    assert "flagged" in r["metrics"]["revenue_mom_pct"]["note"]


# ---------- 12-month growth ---------------------------------------------------------------
def test_12m_growth_needs_24_consecutive_months():
    ms = months(2024, 24)
    rev = [100] * 12 + [110] * 12
    r = run([(m, v, 60, True) for m, v in zip(ms, rev)])
    assert val(r, "revenue_12m_growth_pct") == pytest.approx(10.0)
    r = run([(m, v, 60, True) for m, v in zip(ms[1:], rev[1:])])  # only 23 months
    assert val(r, "revenue_12m_growth_pct") is None
    gap = [(m, v, 60, True) for m, v in zip(ms, rev) if m != "2024-05"]  # hole in prior year
    assert val(run(gap), "revenue_12m_growth_pct") is None


# ---------- trends ---------------------------------------------------------------------------
def test_clear_growth_trend():
    ms = months(2025, 12)
    r = run([(m, 100 + 10 * i, 50, True) for i, m in enumerate(ms)])
    t = r["trend"]["revenue"]
    assert t["direction"] == "increasing" and t["r2"] == pytest.approx(1.0)
    # slope 10 per month, mean 155 -> 6.45 % per month
    assert t["pct_per_month"] == pytest.approx(10 / 155 * 100, abs=0.01)


def test_clear_decline_and_flat():
    ms = months(2025, 12)
    r = run([(m, 300 - 10 * i, 50, True) for i, m in enumerate(ms)])
    assert r["trend"]["revenue"]["direction"] == "decreasing"
    r = run([(m, 100, 50, True) for m in ms])
    assert r["trend"]["revenue"]["direction"] == "flat"


def test_seasonal_noise_is_reported_as_unclear_not_as_a_trend():
    ms = months(2025, 12)
    vals = [100, 160, 90, 170, 80, 180, 95, 165, 85, 175, 100, 150]
    r = run([(m, v, 50, True) for m, v in zip(ms, vals)])
    assert r["trend"]["revenue"]["direction"] == "unclear"
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert f["FIN-REVTREND"]["type"] == "revenue_trend_unclear" and f["FIN-REVTREND"]["severity"] == "info"


def test_trend_needs_six_points():
    r = run([(m, 100 + i, 50, True) for i, m in enumerate(months(2025, 5))])
    assert val(r, "revenue_trend_pct_per_month") is None
    assert "at least 6" in r["metrics"]["revenue_trend_pct_per_month"]["reason"]


def test_trend_respects_calendar_gaps():
    # value rises 10/month; with a missing month the slope must still be 10/month
    ms = [m for m in months(2025, 8) if m != "2025-04"]
    vals = [100 + 10 * (int(m[-2:]) - 1) for m in ms]
    r = run([(m, v, 50, True) for m, v in zip(ms, vals)])
    assert r["trend"]["revenue"]["n_points"] == 7
    mean = sum(vals) / len(vals)
    assert r["trend"]["revenue"]["pct_per_month"] == pytest.approx(10 / mean * 100, abs=0.01)


def test_flagged_month_is_left_out_of_trend():
    ms = months(2025, 9)
    vals = [100, 101, 99, 100, 102, 100, 98, 100, 100000]  # last is an extreme outlier
    r = run([(m, v, 50, True) for m, v in zip(ms, vals)])
    assert "2025-09" in r["flagged_periods"]
    assert r["trend"]["revenue"]["direction"] in ("flat", "unclear")
    assert r["trend"]["revenue"]["n_points"] == 8


# ---------- findings ------------------------------------------------------------------------------
@pytest.mark.parametrize("rev,exp,severity", [(100, 120, "high"), (100, 97, "medium"),
                                                (100, 93, "low"), (100, 70, "info")])
def test_margin_finding_severity(rev, exp, severity):
    r = run([(m, rev, exp, True) for m in months(2025, 3)])
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert f["FIN-MARGIN"]["severity"] == severity
    assert "not an industry benchmark" in f["FIN-MARGIN"]["comparison"]


def test_incomplete_expenses_produce_definition_finding_not_margin():
    r = run([(m, 100, 60, False) for m in months(2025, 3)])
    ids = {x["id"] for x in build_financial_findings(r)}
    assert "FIN-EXPDEF" in ids and "FIN-MARGIN" not in ids


def test_loss_months_counted_even_with_incomplete_list():
    # listed expenses > revenue proves a loss regardless of completeness
    r = run([("2025-01", 100, 150, False), ("2025-02", 100, 60, False), ("2025-03", 100, 120, False)])
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert f["FIN-LOSSMONTHS"]["value"] == 2 and f["FIN-LOSSMONTHS"]["severity"] == "medium"


def test_expenses_outpacing_revenue():
    ms = months(2025, 12)
    r = run([(m, 1000 + 5 * i, 600 + 40 * i, True) for i, m in enumerate(ms)])
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert "FIN-COSTOUTPACE" in f and f["FIN-COSTOUTPACE"]["metric"] == "listed_expenses_trend_pct_per_month"


def test_yoy_decline_finding():
    ms = months(2024, 13)
    r = run([(m, v, 50, True) for m, v in zip(ms, [100] * 12 + [70])])
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert f["FIN-YOYDROP"]["severity"] == "high" and f["FIN-YOYDROP"]["value"] == pytest.approx(-30.0)


def test_flagged_values_surface_as_review_finding_and_are_not_loss_months():
    r = run([("2025-01", 100, 60, True), ("2025-02", -5000, 60, True), ("2025-03", 100, 60, True)])
    f = {x["id"]: x for x in build_financial_findings(r)}
    assert f["FIN-REVIEW"]["value"] == 1
    assert "FIN-LOSSMONTHS" not in f  # the negative revenue is suspicious, not proof of a loss


def test_every_finding_has_required_fields_and_numeric_or_null_value():
    r = run([(m, 100 + i, 90 + 3 * i, True) for i, m in enumerate(months(2025, 12))])
    for f in build_financial_findings(r):
        assert {"id", "type", "metric", "evidence", "severity"} <= f.keys()
        assert f["value"] is None or isinstance(f["value"], float)
        assert f["severity"] in {"info", "low", "medium", "high"}


# ---------- JSON safety & sample data -----------------------------------------------------------------
@pytest.mark.parametrize("scenario", ["retail", "service", "cold_start", "messy"])
def test_result_is_strict_json_for_all_samples(scenario):
    rep = validate_table(pd.read_csv(SAMPLES / scenario / "financials.csv"), "financials")
    res = analyze_financials(rep.clean)
    json.dumps(res, allow_nan=False)  # raises on NaN / numpy types
    json.dumps(build_financial_findings(res), allow_nan=False)


def test_retail_sample_matches_independent_pandas_computation():
    df = pd.read_csv(SAMPLES / "retail" / "financials.csv").sort_values("period")
    last12 = df.tail(12)
    rep = validate_table(df, "financials")
    res = analyze_financials(rep.clean)
    assert val(res, "revenue") == last12["revenue"].sum()
    assert val(res, "profit") == last12["revenue"].sum() - last12["expenses"].sum()
    assert val(res, "profit_margin_pct") == pytest.approx(
        (last12["revenue"].sum() - last12["expenses"].sum()) / last12["revenue"].sum() * 100, abs=0.01)
    prior = df.head(12)["revenue"].sum()
    assert val(res, "revenue_12m_growth_pct") == pytest.approx(
        (last12["revenue"].sum() - prior) / prior * 100, abs=0.01)


def test_service_sample_never_reports_profit():
    rep = validate_table(pd.read_csv(SAMPLES / "service" / "financials.csv"), "financials")
    res = analyze_financials(rep.clean)
    assert val(res, "profit") is None and val(res, "revenue_minus_listed_expenses") is not None
