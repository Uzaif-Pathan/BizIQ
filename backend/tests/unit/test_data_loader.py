"""build_engine_tables: unknown stays unknown, empty tables are None, and the engine accepts the output."""
from datetime import date
from decimal import Decimal

import numpy as np

from analytics_engine import run_analysis
from app.services.data_loader import build_engine_tables


def test_empty_inputs_give_none_not_zero_tables():
    t = build_engine_tables([], [], [])
    assert t == {"financials": None, "customers": None, "products": None}


def test_unknown_values_are_nan_not_zero():
    t = build_engine_tables(
        [{"period_start": date(2025, 1, 1), "revenue": Decimal("1000"), "fixed_expenses": None,
          "variable_expenses": None, "other_expenses": None, "expenses_complete": None}],
        [], [])
    row = t["financials"].iloc[0]
    assert row["period"] == "2025-01" and row["revenue"] == 1000.0
    assert np.isnan(row["expenses"])  # no expense part known -> unknown, not 0
    assert row["expenses_complete"] is None or np.isnan(row["expenses_complete"])


def test_expenses_sum_only_known_parts():
    t = build_engine_tables(
        [{"period_start": date(2025, 1, 1), "revenue": 500, "fixed_expenses": Decimal("100"),
          "variable_expenses": None, "other_expenses": Decimal("50.5"), "expenses_complete": True}], [], [])
    assert t["financials"].iloc[0]["expenses"] == 150.5
    assert bool(t["financials"].iloc[0]["expenses_complete"]) is True


def test_product_cost_priority_and_unknown():
    base = {"period_start": date(2025, 1, 1), "product_id": 7, "item_name": "Rice", "total_revenue": 100}
    t = build_engine_tables([], [], [
        {**base, "units_sold": 10, "unit_cost": Decimal("4"), "total_cost": Decimal("55")},   # total_cost wins
        {**base, "period_start": date(2025, 2, 1), "units_sold": 10, "unit_cost": Decimal("4"), "total_cost": None},
        {**base, "period_start": date(2025, 3, 1), "units_sold": 10, "unit_cost": None, "total_cost": None},
    ])["products"]
    assert t["cost"].iloc[0] == 55.0 and t["cost"].iloc[1] == 40.0 and np.isnan(t["cost"].iloc[2])
    assert (t["product_id"] == "7").all()


def test_engine_runs_on_built_tables_and_keeps_profit_unknown_when_expenses_unknown():
    months = [date(2025, m, 1) for m in range(1, 13)]
    fin = [{"period_start": d, "revenue": 1000 + i * 10, "fixed_expenses": None, "variable_expenses": None,
            "other_expenses": None, "expenses_complete": None} for i, d in enumerate(months)]
    tables = build_engine_tables(fin, [], [])
    res = run_analysis({"business_id": "1", "business_type": "retail"}, tables)
    assert res["status"] in ("completed", "partial")
    assert res["metrics"]["revenue"]["value"] is not None
    assert res["metrics"]["profit"]["value"] is None  # never invented


def test_tables_built_from_rows_give_the_same_metrics_as_the_csv_files():
    """Store the retail sample the way the seed script does, rebuild it, and compare with the CSV run."""
    from pathlib import Path

    import pandas as pd

    samples = Path(__file__).resolve().parents[3] / "data" / "samples" / "retail"
    csv = {t: pd.read_csv(samples / f"{t}.csv") for t in ("financials", "customers", "products")}

    def d(p):
        y, m = p.split("-")
        return date(int(y), int(m), 1)

    fin = [{"period_start": d(r.period), "revenue": r.revenue, "fixed_expenses": None, "variable_expenses": None,
            "other_expenses": r.expenses, "expenses_complete": bool(r.expenses_complete)}
           for r in csv["financials"].itertuples()]
    cus = [{"period_start": d(r.period), "customer_ref": r.customer_id, "transactions": r.transactions,
            "amount_spent": r.amount_spent} for r in csv["customers"].itertuples()]
    pro = [{"period_start": d(r.period), "product_id": r.product_id, "item_name": r.product_name,
            "units_sold": r.units_sold, "total_revenue": r.revenue, "total_cost": r.cost, "unit_cost": None}
           for r in csv["products"].itertuples()]
    business = {"business_id": "1", "business_type": "retail"}
    a = run_analysis(business, csv)
    b = run_analysis(business, build_engine_tables(fin, cus, pro))
    for key, m in a["metrics"].items():
        assert b["metrics"][key]["value"] == m["value"], key
    assert [f["id"] for f in a["findings"]] == [f["id"] for f in b["findings"]]
