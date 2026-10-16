"""Customer analytics from a *validated* customers table (one row per customer per month).

Formulas (window = latest 12 calendar months of the customer data):

* active_customers          = distinct customer_id with a row in the window
* total_customer_spend      = sum of amount_spent in the window
* avg_spend_per_customer    = total_customer_spend / active_customers
* total_transactions        = sum of transactions in the window (rows with a transaction
                              count only; missing counts are not treated as 0)
* avg_transaction_value     = spend / transactions, over rows having BOTH values
* repeat_customer_rate_pct  = customers active in >= 2 different months / active_customers
                              * 100 (needs >= 3 months of customer data in the window)
* avg_monthly_retention_pct = average over consecutive month pairs (both present) of
                              |active in both months| / |active in the first month| * 100
                              (needs >= 2 such pairs)
* returning_customers_latest_month_pct = share of the latest month's customers that
                              also appeared in an earlier month of the data
* top_customer_share_pct    = largest customer's spend / total spend * 100
* top_5_customers_share_pct = five largest customers' spend / total spend * 100
* top_10pct_customers_share_pct = largest 10 % of customers (rounded up) / total spend
                              (needs >= 10 customers)
* customer_data_coverage_pct = total_customer_spend / financial revenue over the same
                              window * 100 (only if the financial revenue is supplied)
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from ..common import clean_number, metric, safe_ratio_pct
from ..trends import latest_window, summarize_trend

MIN_MONTHS_REPEAT = 3
MIN_PAIRS_RETENTION = 2
MIN_CUSTOMERS_DECILE = 10


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "metrics": {}, "monthly": [], "trend": {},
            "coverage": {"months": 0, "customers": 0}, "top_customers": []}


def analyze_customers(clean: pd.DataFrame | None,
                      financial_revenue_in_window: float | None = None,
                      financial_window: tuple[str, str] | None = None) -> dict[str, Any]:
    """Customer metrics. ``financial_*`` are optional and only used for the coverage metric
    (``financial_window`` is ``(first, last)`` of the financial reporting window)."""
    if clean is None or len(clean) == 0:
        return _unavailable("no usable customer data was provided")

    df = clean.copy()
    df["_p"] = pd.PeriodIndex(df["period"], freq="M")
    first, last = df["_p"].min(), df["_p"].max()
    win = latest_window(first, last)
    w = df[df["_p"].isin(win)]
    label = f"{win[0]}/{win[-1]}"
    spend_rows = w[w["amount_spent"].notna()]
    if spend_rows.empty:
        return _unavailable("no valid amount_spent values in the customer data")

    metrics: dict[str, dict[str, Any]] = {}
    customers = spend_rows["customer_id"].nunique()
    total_spend = float(spend_rows["amount_spent"].sum())
    months_present = sorted(spend_rows["_p"].unique())
    n_months = len(months_present)

    metrics["active_customers"] = metric(customers, "customers", period=label,
                                         formula="distinct customers with a row in window")
    metrics["total_customer_spend"] = metric(total_spend, "INR", period=label,
                                             formula="sum of amount_spent in window")
    metrics["avg_spend_per_customer"] = metric(
        total_spend / customers if customers else None, "INR", period=label,
        formula="total_customer_spend / active_customers")

    # --- transactions ---------------------------------------------------------------
    tx = spend_rows[spend_rows["transactions"].notna()]
    if tx.empty:
        for k in ("total_transactions", "avg_transaction_value"):
            metrics[k] = metric(None, "count" if k == "total_transactions" else "INR", period=label,
                                formula=k, reason="no transaction counts were provided")
    else:
        miss = len(spend_rows) - len(tx)
        metrics["total_transactions"] = metric(
            tx["transactions"].sum(), "count", period=label,
            formula="sum of transactions in window",
            note=f"{miss} row(s) without a transaction count were not counted" if miss else None)
        tsum = float(tx["transactions"].sum())
        metrics["avg_transaction_value"] = metric(
            tx["amount_spent"].sum() / tsum if tsum > 0 else None, "INR", period=label,
            formula="amount_spent / transactions over rows having both",
            reason="transaction total is zero")

    # --- repeat customers -----------------------------------------------------------------
    per_cust_months = spend_rows.groupby("customer_id")["_p"].nunique()
    if n_months >= MIN_MONTHS_REPEAT:
        metrics["repeat_customer_rate_pct"] = metric(
            (per_cust_months >= 2).mean() * 100, "percent", period=label,
            formula="customers active in >= 2 different months / active customers * 100")
    else:
        metrics["repeat_customer_rate_pct"] = metric(
            None, "percent", period=label, formula="repeat customers / active customers * 100",
            reason=f"needs at least {MIN_MONTHS_REPEAT} months of customer data "
                   f"(have {n_months})")

    # --- retention (consecutive month pairs) ---------------------------------------------------
    by_month = {p: set(g["customer_id"]) for p, g in spend_rows.groupby("_p")}
    rates = [len(by_month[p] & by_month[p + 1]) / len(by_month[p]) * 100
             for p in by_month if (p + 1) in by_month and by_month[p]]
    if len(rates) >= MIN_PAIRS_RETENTION:
        metrics["avg_monthly_retention_pct"] = metric(
            sum(rates) / len(rates), "percent", period=label,
            formula="average over consecutive month pairs of customers present in both / "
                    "customers in the first month * 100",
            note=f"based on {len(rates)} month pairs")
    else:
        metrics["avg_monthly_retention_pct"] = metric(
            None, "percent", period=label, formula="month-to-month customer retention",
            reason=f"needs at least {MIN_PAIRS_RETENTION} pairs of consecutive months "
                   f"(have {len(rates)})")

    last_in_win = months_present[-1]
    earlier = set(df[(df["_p"] < last_in_win) & df["amount_spent"].notna()]["customer_id"])
    cur = by_month[last_in_win]
    if len(months_present) >= 2 or earlier:
        ret = len(cur & earlier) / len(cur) * 100 if cur else None
        metrics["returning_customers_latest_month_pct"] = metric(
            ret, "percent", period=str(last_in_win),
            formula="latest month's customers who appeared in an earlier month / latest "
                    "month's customers * 100",
            note=f"history in the data: {int(df['_p'].nunique())} month(s); 'new' means first "
                 "seen in the data provided")
    else:
        metrics["returning_customers_latest_month_pct"] = metric(
            None, "percent", period=str(last_in_win), formula="returning customers share",
            reason="only one month of customer data")

    # --- concentration ----------------------------------------------------------------------------------
    per_cust = spend_rows.groupby("customer_id")["amount_spent"].sum().sort_values(ascending=False)
    pos_total = float(per_cust.clip(lower=0).sum())
    top_customers = [{"customer_id": cid, "spend": clean_number(v),
                      "share_pct": clean_number(safe_ratio_pct(v, pos_total))}
                     for cid, v in per_cust.head(5).items()]
    metrics["top_customer_share_pct"] = metric(
        safe_ratio_pct(per_cust.iloc[0], pos_total), "percent", period=label,
        formula="largest customer's spend / total spend * 100",
        reason="total customer spend is not positive")
    metrics["top_5_customers_share_pct"] = metric(
        safe_ratio_pct(per_cust.head(5).sum(), pos_total), "percent", period=label,
        formula="five largest customers' spend / total spend * 100",
        reason="total customer spend is not positive",
        note=None if customers > 5 else f"only {customers} customer(s) in total")
    if customers >= MIN_CUSTOMERS_DECILE:
        k = math.ceil(customers * 0.10)
        metrics["top_10pct_customers_share_pct"] = metric(
            safe_ratio_pct(per_cust.head(k).sum(), pos_total), "percent", period=label,
            formula=f"spend of the largest 10% of customers ({k} of {customers}) / total spend * 100",
            reason="total customer spend is not positive")
    else:
        metrics["top_10pct_customers_share_pct"] = metric(
            None, "percent", period=label, formula="top 10% customers' share of spend",
            reason=f"needs at least {MIN_CUSTOMERS_DECILE} customers (have {customers})")

    # --- coverage vs financial revenue --------------------------------------------------------------------
    same_window = financial_window is None or financial_window == (str(win[0]), str(win[-1]))
    if financial_revenue_in_window and financial_revenue_in_window > 0 and same_window:
        cov = safe_ratio_pct(total_spend, financial_revenue_in_window)
        metrics["customer_data_coverage_pct"] = metric(
            cov, "percent", period=label,
            formula="total_customer_spend / financial revenue (same window) * 100",
            note="above 100 means customer spend exceeds reported revenue; check the data"
            if cov and cov > 100 else None)
    else:
        metrics["customer_data_coverage_pct"] = metric(
            None, "percent", period=label, formula="customer spend / financial revenue * 100",
            reason="financial revenue for the same period was not available")

    # --- monthly series + trend of active customers -----------------------------------------------------------
    full = pd.period_range(win[0], win[-1], freq="M")
    g = spend_rows.groupby("_p")
    cnt = g["customer_id"].nunique().reindex(full)
    spend = g["amount_spent"].sum().reindex(full)
    trans = tx.groupby("_p")["transactions"].sum().reindex(full)
    monthly = [{"period": str(p), "active_customers": None if pd.isna(cnt[p]) else int(cnt[p]),
                "spend": clean_number(spend[p]), "transactions": clean_number(trans[p], 0)}
               for p in full]
    trend = {"active_customers": summarize_trend(cnt)}
    t = trend["active_customers"]
    metrics["active_customers_trend_pct_per_month"] = metric(
        t["pct_per_month"], "percent_per_month", period=label,
        formula="least-squares slope of monthly active customers / mean * 100",
        reason=t["reason"])

    flagged = int(w["needs_review"].sum()) if "needs_review" in w else 0
    return {"available": True, "reason": None, "metrics": metrics, "monthly": monthly,
            "trend": trend, "top_customers": top_customers,
            "coverage": {"months": n_months, "customers": int(customers),
                         "window_first": str(win[0]), "window_last": str(win[-1]),
                         "rows_flagged_for_review": flagged}}
