"""Product / service analytics from a *validated* products table (product x month rows).

Formulas (window = latest 12 calendar months of the product data):

* revenue (per product)   = sum of revenue in the window
* units_sold              = sum of units_sold (rows with a value only; null if none)
* cost                    = sum of cost, but ONLY if every revenue row of that product has a
                            cost; otherwise null (a partial cost sum would overstate margin)
* gross_profit            = revenue - cost                         (needs cost)
* gross_margin_pct        = gross_profit / revenue * 100           (needs cost, revenue > 0)
* revenue_share_pct       = product revenue / total product revenue * 100
* revenue_trend           = least-squares trend of the product's monthly revenue
* share_trend             = same on the product's monthly share of that month's total product
                            revenue (in percentage points per month); not distorted by
                            business-wide seasonality
* top_product_share_pct   = largest product's share of total product revenue
* top_3_products_share_pct= three largest products' share (needs > 3 products)
* gross_margin_pct (overall) = (total revenue - total cost) / total revenue * 100, only if cost
                            is known for every product row in the window
* product_data_coverage_pct = total product revenue / financial revenue (same window) * 100

A product with no row in a month is "no data" for that month, not zero sales.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..common import clean_number, metric, safe_ratio_pct
from ..trends import latest_window, summarize_trend

MIN_PRODUCTS_TOP3 = 4


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "metrics": {}, "products": [],
            "top_performers": [], "low_performers": [], "coverage": {"products": 0, "months": 0}}


def analyze_products(clean: pd.DataFrame | None,
                     financial_revenue_in_window: float | None = None,
                     financial_window: tuple[str, str] | None = None) -> dict[str, Any]:
    if clean is None or len(clean) == 0:
        return _unavailable("no usable product data was provided")

    df = clean.copy()
    df["_p"] = pd.PeriodIndex(df["period"], freq="M")
    win = latest_window(df["_p"].min(), df["_p"].max())
    w = df[df["_p"].isin(win) & df["revenue"].notna()]
    if w.empty:
        return _unavailable("no valid revenue values in the product data")
    label = f"{win[0]}/{win[-1]}"

    total_rev = float(w["revenue"].sum())
    monthly_total = w.groupby("_p")["revenue"].sum().reindex(win)

    rows: list[dict[str, Any]] = []
    for pid, g in w.groupby("product_id"):
        rev = float(g["revenue"].sum())
        names = g["product_name"].dropna() if "product_name" in g else pd.Series(dtype=object)
        name = str(names.iloc[-1]) if len(names) else str(pid)
        units = g["units_sold"].dropna()
        cost_known = bool(g["cost"].notna().all())
        cost = float(g["cost"].sum()) if cost_known else None
        gp = rev - cost if cost is not None else None
        series = g.set_index("_p")["revenue"].reindex(win)
        share = (series / monthly_total * 100).where(monthly_total > 0)
        rows.append({
            "product_id": str(pid), "product_name": name,
            "months_active": int(g["_p"].nunique()),
            "revenue": clean_number(rev), "units_sold": clean_number(units.sum(), 0) if len(units) else None,
            "cost": clean_number(cost), "gross_profit": clean_number(gp),
            "gross_margin_pct": clean_number(safe_ratio_pct(gp, rev)) if gp is not None else None,
            "revenue_share_pct": clean_number(safe_ratio_pct(rev, total_rev)),
            "revenue_trend": summarize_trend(series),
            "share_trend": summarize_trend(share),
            "cost_note": None if cost_known else "cost missing for some months; margin not computed",
        })

    rows.sort(key=lambda r: r["revenue"] or 0, reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank_by_revenue"] = i
    gp_sorted = sorted([r for r in rows if r["gross_profit"] is not None],
                       key=lambda r: r["gross_profit"], reverse=True)
    for i, r in enumerate(gp_sorted, 1):
        r["rank_by_gross_profit"] = i
    for r in rows:
        r.setdefault("rank_by_gross_profit", None)

    n = len(rows)
    k = min(3, n // 2)
    top = [r["product_id"] for r in rows[:k]]
    low = [r["product_id"] for r in rows[::-1][:k]]

    metrics: dict[str, dict[str, Any]] = {
        "product_count": metric(n, "products", period=label, formula="distinct products with revenue in window"),
        "total_product_revenue": metric(total_rev, "INR", period=label,
                                        formula="sum of product revenue in window"),
    }
    if n >= 2:
        metrics["top_product_share_pct"] = metric(
            rows[0]["revenue_share_pct"], "percent", period=label,
            formula="largest product's revenue / total product revenue * 100")
    else:
        metrics["top_product_share_pct"] = metric(
            None, "percent", period=label, formula="largest product's share",
            reason="needs at least 2 products to compare")
    if n >= MIN_PRODUCTS_TOP3:
        metrics["top_3_products_share_pct"] = metric(
            safe_ratio_pct(sum(r["revenue"] for r in rows[:3]), total_rev), "percent", period=label,
            formula="three largest products' revenue / total product revenue * 100")
    else:
        metrics["top_3_products_share_pct"] = metric(
            None, "percent", period=label, formula="top 3 products' share",
            reason=f"needs more than 3 products (have {n})")

    all_cost = bool(w["cost"].notna().all())
    if all_cost:
        cost_total = float(w["cost"].sum())
        gp_total = total_rev - cost_total
        metrics["gross_profit"] = metric(gp_total, "INR", period=label,
                                         formula="product revenue - product cost")
        metrics["gross_margin_pct"] = metric(
            safe_ratio_pct(gp_total, total_rev), "percent", period=label,
            formula="(product revenue - product cost) / product revenue * 100",
            reason="product revenue is not positive")
    else:
        n_missing = int(w["cost"].isna().sum())
        for key, unit in (("gross_profit", "INR"), ("gross_margin_pct", "percent")):
            metrics[key] = metric(None, unit, period=label, formula="product revenue - product cost",
                                  reason=f"cost is missing for {n_missing} product row(s)")
    neg = [r for r in rows if r["gross_margin_pct"] is not None and r["gross_margin_pct"] < 0]
    known = [r for r in rows if r["gross_margin_pct"] is not None]
    metrics["products_with_negative_margin"] = metric(
        len(neg) if known else None, "products", period=label,
        formula="products whose cost exceeds revenue (cost known)",
        reason="no product has complete cost data",
        note=None if len(known) == n else f"cost known for {len(known)} of {n} products")

    same_window = financial_window is None or financial_window == (str(win[0]), str(win[-1]))
    if financial_revenue_in_window and financial_revenue_in_window > 0 and same_window:
        metrics["product_data_coverage_pct"] = metric(
            safe_ratio_pct(total_rev, financial_revenue_in_window), "percent", period=label,
            formula="total product revenue / financial revenue (same window) * 100")
    else:
        metrics["product_data_coverage_pct"] = metric(
            None, "percent", period=label, formula="product revenue / financial revenue * 100",
            reason="financial revenue for the same period was not available")

    return {"available": True, "reason": None, "metrics": metrics, "products": rows,
            "top_performers": top, "low_performers": low,
            "coverage": {"products": n, "months": int(w["_p"].nunique()),
                         "window_first": str(win[0]), "window_last": str(win[-1]),
                         "rows_flagged_for_review": int(w["needs_review"].sum())
                         if "needs_review" in w else 0}}
