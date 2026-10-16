"""Customer analytics tests with hand-computed expectations."""

import json

import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.customers import analyze_customers, build_customer_findings
from analytics_engine.validation import validate_table

COLS = ("period", "customer_id", "amount_spent", "transactions")


def run(rows, rev=None, window=None, cols=COLS):
    rep = validate_table(pd.DataFrame(rows, columns=list(cols)), "customers")
    return analyze_customers(rep.clean, rev, window)


def val(res, key):
    return res["metrics"][key]["value"]


def months(n, year=2025, start=1):
    return [f"{year + (start - 1 + i) // 12}-{(start - 1 + i) % 12 + 1:02d}" for i in range(n)]


# A buys every month, B in Jan+Mar, C only in Feb  (spend 100 each time)
BASIC = [("2025-01", "A", 100, 2), ("2025-01", "B", 100, 4),
         ("2025-02", "A", 100, 2), ("2025-02", "C", 100, 2),
         ("2025-03", "A", 100, 1), ("2025-03", "B", 100, 1)]


def test_totals_and_averages():
    r = run(BASIC)
    assert val(r, "active_customers") == 3
    assert val(r, "total_customer_spend") == 600
    assert val(r, "avg_spend_per_customer") == 200
    assert val(r, "total_transactions") == 12
    assert val(r, "avg_transaction_value") == 50  # 600 / 12


def test_repeat_rate_counts_customers_active_in_two_or_more_months():
    assert val(run(BASIC), "repeat_customer_rate_pct") == pytest.approx(66.67, abs=0.01)  # A, B of 3


def test_retention_is_average_over_consecutive_pairs():
    # Jan->Feb: {A,B} & {A,C} = {A} -> 1/2 ; Feb->Mar: {A,C} & {A,B} = {A} -> 1/2
    assert val(run(BASIC), "avg_monthly_retention_pct") == pytest.approx(50.0)


def test_returning_customers_latest_month():
    assert val(run(BASIC), "returning_customers_latest_month_pct") == 100.0  # A and B both seen before


def test_concentration_small_customer_base():
    r = run(BASIC)
    assert val(r, "top_customer_share_pct") == 50.0  # A: 300 of 600
    assert val(r, "top_5_customers_share_pct") == 100.0
    assert "only 3 customer" in r["metrics"]["top_5_customers_share_pct"]["note"]
    assert val(r, "top_10pct_customers_share_pct") is None
    assert "at least 10" in r["metrics"]["top_10pct_customers_share_pct"]["reason"]
    assert r["top_customers"][0] == {"customer_id": "A", "spend": 300.0, "share_pct": 50.0}


def test_concentration_with_ten_customers():
    rows = [("2025-01", "BIG", 91, 1)] + [("2025-01", f"S{i}", 1, 1) for i in range(9)]
    r = run(rows)
    assert val(r, "top_customer_share_pct") == 91.0
    assert val(r, "top_5_customers_share_pct") == 95.0  # 91 + 4
    assert val(r, "top_10pct_customers_share_pct") == 91.0  # ceil(10 * 0.1) = 1 customer


def test_missing_transaction_counts_are_not_zero():
    rows = [("2025-01", "A", 100, 2), ("2025-01", "B", 100, None), ("2025-02", "A", 100, 2)]
    r = run(rows)
    assert val(r, "total_transactions") == 4
    assert "1 row(s) without a transaction count" in r["metrics"]["total_transactions"]["note"]
    assert val(r, "avg_transaction_value") == 50  # B has no count, so only A: (100 + 100) / (2 + 2)
    r2 = run([("2025-01", "A", 100, None)])
    assert val(r2, "total_transactions") is None and val(r2, "avg_transaction_value") is None


def test_transactions_column_absent_entirely():
    r = run([("2025-01", "A", 100), ("2025-02", "A", 50)], cols=("period", "customer_id", "amount_spent"))
    assert val(r, "total_transactions") is None
    assert "no transaction counts" in r["metrics"]["total_transactions"]["reason"]
    assert val(r, "total_customer_spend") == 150


def test_repeat_rate_needs_three_months():
    r = run([("2025-01", "A", 100, 1), ("2025-02", "A", 100, 1)])
    assert val(r, "repeat_customer_rate_pct") is None
    assert "at least 3 months" in r["metrics"]["repeat_customer_rate_pct"]["reason"]


def test_retention_needs_two_consecutive_pairs_and_ignores_gaps():
    assert val(run([("2025-01", "A", 1, 1), ("2025-02", "A", 1, 1)]), "avg_monthly_retention_pct") is None
    gap = [("2025-01", "A", 1, 1), ("2025-03", "A", 1, 1), ("2025-05", "A", 1, 1)]
    r = run(gap)
    assert val(r, "avg_monthly_retention_pct") is None  # no consecutive months at all


def test_single_month_has_no_returning_metric():
    r = run([("2025-01", "A", 100, 1), ("2025-01", "B", 100, 1)])
    assert val(r, "returning_customers_latest_month_pct") is None
    assert r["available"]


def test_only_latest_12_months_counted_but_history_used_for_returning():
    rows = [("2024-01", "OLD", 500, 1)] + [(m, "A", 10, 1) for m in months(12)] + [("2025-12", "OLD", 5, 1)]
    r = run(rows)
    assert r["coverage"]["window_first"] == "2025-01"
    assert val(r, "total_customer_spend") == 125  # 12 * 10 + 5; the 2024 purchase is outside
    assert val(r, "active_customers") == 2
    assert val(r, "returning_customers_latest_month_pct") == 100.0  # OLD bought in 2024


def test_coverage_against_financial_revenue():
    r = run(BASIC, rev=1000, window=("2025-01", "2025-03"))
    assert val(r, "customer_data_coverage_pct") == 60.0
    assert val(run(BASIC), "customer_data_coverage_pct") is None
    other = run(BASIC, rev=1000, window=("2024-06", "2025-05"))  # different window -> not comparable
    assert val(other, "customer_data_coverage_pct") is None


def test_active_customer_trend():
    rows = []
    for i, m in enumerate(months(8)):
        rows += [(m, f"C{j}", 10, 1) for j in range(5 + i)]  # 5, 6, 7 ... customers
    r = run(rows)
    assert r["trend"]["active_customers"]["direction"] == "increasing"
    assert r["monthly"][0]["active_customers"] == 5 and r["monthly"][-1]["active_customers"] == 12


def test_unavailable_when_no_data():
    for clean in (None, pd.DataFrame()):
        r = analyze_customers(clean)
        assert r["available"] is False and r["reason"] and r["metrics"] == {}
        assert build_customer_findings(r) == []


def test_all_amounts_missing_is_unavailable_not_zero_spend():
    r = run([("2025-01", "A", None, 1), ("2025-02", "B", None, 1)])
    assert r["available"] is False


# ---------- findings ----------------------------------------------------------------
def f(res):
    return {x["id"]: x for x in build_customer_findings(res)}


def one_time_buyers(n_months=4, per_month=5):
    return [(m, f"{m}-{j}", 100, 1) for m in months(n_months) for j in range(per_month)]


def test_weak_repeat_and_low_retention_findings():
    r = run(one_time_buyers())
    found = f(r)
    assert found["CUS-REPEAT"]["type"] == "repeat_customers_low" and found["CUS-REPEAT"]["severity"] == "medium"
    assert found["CUS-RETENTION"]["severity"] == "high"  # 0% come back


def test_healthy_repeat_is_info():
    r = run([(m, c, 100, 1) for m in months(4) for c in "ABCDE"])
    assert f(r)["CUS-REPEAT"]["severity"] == "info" and f(r)["CUS-RETENTION"]["severity"] == "info"


def test_high_concentration_finding():
    rows = [("2025-01", "BIG", 900, 1)] + [("2025-01", f"S{i}", 11.11, 1) for i in range(9)]
    found = f(run(rows))
    assert found["CUS-CONC"]["severity"] == "high"
    assert "largest customer 90% of spend" in found["CUS-CONC"]["evidence"]


def test_no_concentration_finding_for_tiny_customer_base():
    assert "CUS-CONC" not in f(run([("2025-01", "A", 100, 1), ("2025-01", "B", 100, 1)]))


def test_low_coverage_finding():
    found = f(run(BASIC, rev=10000, window=("2025-01", "2025-03")))
    assert found["CUS-COVERAGE"]["value"] == 6.0


def test_flagged_rows_finding():
    r = run(BASIC + [("2025-03", "D", -50, 1)])
    assert "CUS-REVIEW" in f(r)


def test_customer_findings_have_required_fields():
    for x in build_customer_findings(run(BASIC)):
        assert {"id", "type", "metric", "evidence", "severity"} <= x.keys()
        assert x["severity"] in {"info", "low", "medium", "high"}


# ---------- samples ----------------------------------------------------------------------
@pytest.mark.parametrize("scenario", ["retail", "service"])
def test_samples_are_strict_json(scenario):
    rep = validate_table(pd.read_csv(SAMPLES / scenario / "customers.csv"), "customers")
    res = analyze_customers(rep.clean)
    json.dumps(res, allow_nan=False)
    json.dumps(build_customer_findings(res), allow_nan=False)


def test_retail_sample_matches_independent_pandas_computation():
    df = pd.read_csv(SAMPLES / "retail" / "customers.csv")
    d25 = df[df.period.str.startswith("2025")]
    res = analyze_customers(validate_table(df, "customers").clean)
    assert val(res, "active_customers") == d25.customer_id.nunique()
    assert val(res, "total_customer_spend") == pytest.approx(d25.amount_spent.sum(), abs=0.01)
    months_per_cust = d25.groupby("customer_id").period.nunique()
    assert val(res, "repeat_customer_rate_pct") == pytest.approx((months_per_cust >= 2).mean() * 100, abs=0.01)
