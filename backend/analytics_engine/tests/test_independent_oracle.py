"""Independent re-computation of headline metrics with the standard library only (csv, statistics).

Nothing here imports pandas or the engine's calculation code, so a bug in the engine's formulas
cannot also be in the oracle. Window = latest 12 months with revenue, as documented in ENGINE_FORMULAS.md.
"""
import csv
from collections import defaultdict

import pandas as pd
import pytest

from analytics_engine.pipeline import run_analysis
from conftest import SAMPLES


def _rows(scn, table):
    with open(SAMPLES / scn / f"{table}.csv", newline="") as f:
        return list(csv.DictReader(f))


def _window(fin):
    months = sorted(r["period"] for r in fin if r["revenue"].strip())
    return set(months[-12:])


def _engine(scn, btype):
    data = {t: pd.read_csv(SAMPLES / scn / f"{t}.csv") for t in ("financials", "customers", "products")
            if (SAMPLES / scn / f"{t}.csv").exists()}
    return run_analysis({"business_id": "b", "business_type": btype}, data)["metrics"]


@pytest.mark.parametrize("scn,btype", [("retail", "retail"), ("service", "service")])
def test_financial_metrics_match_oracle(scn, btype):
    m = _engine(scn, btype)
    fin = _rows(scn, "financials")
    w = _window(fin)
    rows = [r for r in fin if r["period"] in w]
    rev = sum(float(r["revenue"]) for r in rows)
    listed = sum(float(r["expenses"]) for r in rows if r["expenses"].strip())
    assert m["revenue"]["value"] == pytest.approx(rev)
    assert m["listed_expenses"]["value"] == pytest.approx(listed)
    if all(r["expenses_complete"].strip().lower() == "true" for r in rows):
        assert m["expenses"]["value"] == pytest.approx(listed)
        assert m["profit"]["value"] == pytest.approx(rev - listed)
        assert m["profit_margin_pct"]["value"] == pytest.approx(round((rev - listed) / rev * 100, 2), abs=0.01)
    else:  # expense list not complete -> profit must NOT be reported (never assume missing costs are zero)
        assert m["expenses"]["value"] is None and m["profit"]["value"] is None
        assert m["profit_margin_pct"]["value"] is None
    ordered = sorted(rows, key=lambda r: r["period"])
    last, prev = float(ordered[-1]["revenue"]), float(ordered[-2]["revenue"])
    assert m["revenue_mom_pct"]["value"] == pytest.approx(round((last - prev) / prev * 100, 2), abs=0.01)


@pytest.mark.parametrize("scn,btype", [("retail", "retail"), ("service", "service")])
def test_customer_metrics_match_oracle(scn, btype):
    m = _engine(scn, btype)
    w = _window(_rows(scn, "financials"))
    rows = [r for r in _rows(scn, "customers") if r["period"] in w]
    spend, months, tx = defaultdict(float), defaultdict(set), 0
    for r in rows:
        spend[r["customer_id"]] += float(r["amount_spent"]); months[r["customer_id"]].add(r["period"])
        tx += int(float(r["transactions"]))
    total = sum(spend.values())
    assert m["active_customers"]["value"] == len(spend)
    assert m["total_customer_spend"]["value"] == pytest.approx(total, abs=0.01)
    assert m["total_transactions"]["value"] == tx
    assert m["repeat_customer_rate_pct"]["value"] == pytest.approx(
        round(sum(len(v) >= 2 for v in months.values()) / len(spend) * 100, 2), abs=0.01)
    ranked = sorted(spend.values(), reverse=True)
    assert m["top_customer_share_pct"]["value"] == pytest.approx(round(ranked[0] / total * 100, 2), abs=0.01)
    assert m["top_5_customers_share_pct"]["value"] == pytest.approx(round(sum(ranked[:5]) / total * 100, 2), abs=0.01)


@pytest.mark.parametrize("scn,btype", [("retail", "retail")])
def test_product_metrics_match_oracle(scn, btype):
    m = _engine(scn, btype)
    w = _window(_rows(scn, "financials"))
    rev, cost = defaultdict(float), 0.0
    for r in _rows(scn, "products"):
        if r["period"] in w:
            rev[r["product_id"]] += float(r["revenue"]); cost += float(r["cost"])
    total = sum(rev.values())
    ranked = sorted(rev.values(), reverse=True)
    assert m["product_count"]["value"] == len(rev)
    assert m["total_product_revenue"]["value"] == pytest.approx(total, abs=0.01)
    assert m["top_product_share_pct"]["value"] == pytest.approx(round(ranked[0] / total * 100, 2), abs=0.01)
    assert m["top_3_products_share_pct"]["value"] == pytest.approx(round(sum(ranked[:3]) / total * 100, 2), abs=0.01)
    assert m["gross_profit"]["value"] == pytest.approx(total - cost, abs=0.01)
    assert m["gross_margin_pct"]["value"] == pytest.approx(round((total - cost) / total * 100, 2), abs=0.01)
