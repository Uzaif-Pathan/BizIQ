"""Builds the three tables the analytics engine reads from rows stored in the database.

Rules (the same ones the engine follows):
* a table with no rows is ``None`` (the engine then skips that analysis); never a table of zeros;
* an unknown value stays unknown (NaN / None), never 0;
* expenses are the sum of the expense parts that are known; if none is known they are unknown.

``build_engine_tables`` is pure (no database) so it can be tested alone; ``load_engine_data`` reads
the rows for one business from the database and calls it.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

import numpy as np
import pandas as pd


def _num(value: Any) -> float:
    return float("nan") if value is None else float(value)


def _period(d: Any) -> str:
    return d.strftime("%Y-%m")


def _expenses(row: Mapping[str, Any]) -> float:
    parts = [row.get("fixed_expenses"), row.get("variable_expenses"), row.get("other_expenses")]
    known = [float(p) for p in parts if p is not None]
    return float(sum(known)) if known else float("nan")


def build_engine_tables(
    financial_rows: Iterable[Mapping[str, Any]],
    customer_rows: Iterable[Mapping[str, Any]],
    product_rows: Iterable[Mapping[str, Any]],
) -> Dict[str, Optional[pd.DataFrame]]:
    fin = [
        {
            "period": _period(r["period_start"]),
            "revenue": _num(r.get("revenue")),
            "expenses": _expenses(r),
            "expenses_complete": r.get("expenses_complete"),  # True / False / None (= not stated)
        }
        for r in financial_rows
    ]
    cus = [
        {
            "period": _period(r["period_start"]),
            "customer_id": str(r["customer_ref"]),
            "transactions": _num(r.get("transactions")),
            "amount_spent": _num(r.get("amount_spent")),
        }
        for r in customer_rows
    ]
    pro = []
    for r in product_rows:
        units, unit_cost, total_cost = r.get("units_sold"), r.get("unit_cost"), r.get("total_cost")
        if total_cost is not None:
            cost = float(total_cost)
        elif units is not None and unit_cost is not None:
            cost = float(units) * float(unit_cost)
        else:
            cost = float("nan")  # cost unknown: margin is not calculated
        pro.append(
            {
                "period": _period(r["period_start"]),
                "product_id": str(r["product_id"]),
                "product_name": r.get("item_name"),
                "units_sold": _num(units),
                "revenue": _num(r.get("total_revenue")),
                "cost": cost,
            }
        )

    def frame(rows, columns):
        return pd.DataFrame(rows, columns=columns) if rows else None

    fin_df = frame(fin, ["period", "revenue", "expenses", "expenses_complete"])
    if fin_df is not None:
        fin_df["expenses_complete"] = fin_df["expenses_complete"].astype(object).where(
            fin_df["expenses_complete"].notna(), np.nan
        )
    return {
        "financials": fin_df,
        "customers": frame(cus, ["period", "customer_id", "transactions", "amount_spent"]),
        "products": frame(pro, ["period", "product_id", "product_name", "units_sold", "revenue", "cost"]),
    }


def load_engine_data(db, business_id: int) -> Dict[str, Optional[pd.DataFrame]]:
    """Read one business's rows and build the engine tables. ``db`` is a SQLAlchemy Session."""
    from sqlalchemy import select

    from app.models import CustomerActivity, MonthlyFinancial, MonthlyProductMetric, ProductService

    def rows(stmt):
        return [dict(r._mapping) for r in db.execute(stmt)]

    financials = rows(
        select(
            MonthlyFinancial.period_start, MonthlyFinancial.revenue, MonthlyFinancial.fixed_expenses,
            MonthlyFinancial.variable_expenses, MonthlyFinancial.other_expenses, MonthlyFinancial.expenses_complete,
        )
        .where(MonthlyFinancial.business_id == business_id)
        .order_by(MonthlyFinancial.period_start)
    )
    customers = rows(
        select(
            CustomerActivity.period_start, CustomerActivity.customer_ref,
            CustomerActivity.transactions, CustomerActivity.amount_spent,
        )
        .where(CustomerActivity.business_id == business_id)
        .order_by(CustomerActivity.period_start)
    )
    products = rows(
        select(
            MonthlyProductMetric.period_start, ProductService.product_id, ProductService.item_name,
            ProductService.unit_cost, MonthlyProductMetric.units_sold,
            MonthlyProductMetric.total_revenue, MonthlyProductMetric.total_cost,
        )
        .join(ProductService, ProductService.product_id == MonthlyProductMetric.product_id)
        .where(ProductService.business_id == business_id)
        .order_by(MonthlyProductMetric.period_start)
    )
    return build_engine_tables(financials, customers, products)
