"""Financial metrics from a *validated* financials table (output of ``validate_table``).

Formulas (all money in INR, percentages as percent numbers, 23.29 = 23.29 %):

* Reporting window     = the latest 12 calendar months ending at the last period in the
                         data (fewer if the history is shorter). Calendar gaps are real
                         gaps -- missing months are never shifted, filled or set to 0.
* revenue              = sum of revenue over months in the window that have a revenue value
* listed_expenses      = sum of the expenses that were listed (always computed if present)
* expenses             = listed_expenses, but ONLY if the business marked its expense list
                         complete (``expenses_complete`` true for every month used);
                         otherwise null -- an incomplete list is not "total expenses"
* revenue_minus_listed_expenses = revenue - listed_expenses over months having both values
* profit               = revenue - expenses; null unless the expense list is complete AND
                         every revenue month in the window has an expense value
* profit_margin_pct    = profit / revenue * 100, only if profit exists and revenue > 0
* expense_ratio_pct    = expenses / revenue * 100, same conditions as profit
* *_mom_pct            = (latest month - previous calendar month) / previous * 100,
                         only if that previous month exists and is > 0
* *_yoy_pct            = same month one year earlier, same rules
* revenue_12m_growth_pct = revenue of the window vs the 12 months before it; only if both
                         windows are fully covered (12 of 12 months)
* *_trend_pct_per_month = least-squares slope of the monthly series / its mean * 100;
                         needs >= MIN_TREND_POINTS monthly points in the window
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..common import clean_number, metric, pct_change, safe_ratio_pct
from ..trends import WINDOW_MONTHS, latest_window, summarize_trend


def _range(first: pd.Period, last: pd.Period) -> str:
    return f"{first}/{last}"


def analyze_financials(clean: pd.DataFrame | None) -> dict[str, Any]:
    """Compute financial metrics. Never raises on valid-shaped input.

    Returns ``{"metrics", "monthly", "trend", "coverage", "flagged_periods"}``.
    With no usable data, ``metrics`` is empty and ``coverage['months_with_revenue']`` is 0.
    """
    empty = {"metrics": {}, "monthly": [], "trend": {}, "flagged_periods": [],
             "coverage": {"months_with_revenue": 0, "first_period": None, "last_period": None,
                          "window_first": None, "window_last": None, "window_months": 0,
                          "missing_periods": [], "expenses_complete": None}}
    if clean is None or len(clean) == 0:
        return empty

    df = clean.copy()
    df["_p"] = pd.PeriodIndex(df["period"], freq="M")
    df = df.set_index("_p").sort_index()
    first, last = df.index.min(), df.index.max()
    full = pd.period_range(first, last, freq="M")
    rev_all = df["revenue"].reindex(full)
    exp_all = df["expenses"].reindex(full)
    flag_all = df["expenses_complete"].reindex(full)
    review_all = df["needs_review"].reindex(full)

    win = latest_window(first, last)
    w_first = win[0]
    rev, exp, flag = rev_all.loc[win], exp_all.loc[win], flag_all.loc[win]
    win_label = _range(w_first, last)

    rev_months = rev.dropna()
    paired = rev.notna() & exp.notna()
    metrics: dict[str, dict[str, Any]] = {}

    # --- revenue ---------------------------------------------------------
    if rev_months.empty:
        metrics["revenue"] = metric(None, "INR", period=win_label, formula="sum of monthly revenue",
                                    reason="no revenue values in the reporting window")
    else:
        n_missing = len(win) - len(rev_months)
        metrics["revenue"] = metric(
            rev_months.sum(), "INR", period=win_label, formula="sum of monthly revenue in window",
            note=(f"based on {len(rev_months)} of {len(win)} months; "
                  f"{n_missing} month(s) without revenue were not counted (not treated as 0)")
            if n_missing else None)
    metrics["months_of_data"] = metric(len(rev_months), "months", period=win_label,
                                       formula="count of months with a revenue value in window")

    # --- expenses / profit -------------------------------------------------
    listed = exp.dropna()
    if listed.empty:
        for k in ("listed_expenses", "expenses"):
            metrics[k] = metric(None, "INR", period=win_label, formula="sum of listed expenses",
                                reason="no expense values were provided")
    else:
        metrics["listed_expenses"] = metric(
            listed.sum(), "INR", period=win_label,
            formula="sum of expenses that were listed in window")

    exp_paired_flags = flag[paired]
    complete = bool(paired.any()) and bool((exp_paired_flags == True).all())  # noqa: E712
    if paired.any() and not complete:
        n_false = int((exp_paired_flags == False).sum())  # noqa: E712
        n_unknown = int(exp_paired_flags.isna().sum())
        why = ("expense definition incomplete: the business marked its expense list incomplete"
               if n_false and not n_unknown else
               "expense definition unknown: expenses_complete was not provided"
               if n_unknown and not n_false else
               "expense definition incomplete or unknown for some months")
    else:
        why = None

    all_rev_have_exp = bool(paired.any()) and int(paired.sum()) == len(rev_months)
    profit_ok = complete and all_rev_have_exp

    if not listed.empty:
        if complete:
            metrics["expenses"] = metric(listed.sum(), "INR", period=win_label,
                                         formula="sum of expenses (expense list marked complete)")
        else:
            metrics["expenses"] = metric(None, "INR", period=win_label,
                                         formula="sum of expenses (only if expense list complete)",
                                         reason=why or "no month has both revenue and expenses")

    if paired.any():
        rmle = float(rev[paired].sum() - exp[paired].sum())
        metrics["revenue_minus_listed_expenses"] = metric(
            rmle, "INR", period=win_label,
            formula="revenue - listed expenses, over months having both",
            note=None if int(paired.sum()) == len(win) else
            f"based on {int(paired.sum())} of {len(win)} months")
    else:
        metrics["revenue_minus_listed_expenses"] = metric(
            None, "INR", period=win_label, formula="revenue - listed expenses",
            reason="no month has both revenue and expenses")

    if profit_ok:
        profit = float(rev[paired].sum() - exp[paired].sum())
        metrics["profit"] = metric(profit, "INR", period=win_label,
                                   formula="revenue - expenses (expense list complete)")
        margin = safe_ratio_pct(profit, rev[paired].sum())
        metrics["profit_margin_pct"] = metric(
            margin, "percent", period=win_label, formula="profit / revenue * 100",
            reason=None if margin is not None else "revenue is not positive")
        ratio = safe_ratio_pct(exp[paired].sum(), rev[paired].sum())
        metrics["expense_ratio_pct"] = metric(
            ratio, "percent", period=win_label, formula="expenses / revenue * 100",
            reason=None if ratio is not None else "revenue is not positive")
    else:
        reason = why or ("expenses are missing for some months that have revenue"
                         if paired.any() else "no month has both revenue and expenses")
        for k, f in (("profit", "revenue - expenses"), ("profit_margin_pct", "profit / revenue * 100"),
                     ("expense_ratio_pct", "expenses / revenue * 100")):
            metrics[k] = metric(None, "percent" if k.endswith("_pct") else "INR",
                                period=win_label, formula=f, reason=reason)

    # --- month-on-month / year-on-year (latest month, calendar based) --------
    latest = last
    prev_m, prev_y = latest - 1, latest - 12

    def at(series: pd.Series, p: pd.Period) -> float | None:
        return clean_number(series.get(p), 10) if p in series.index else None

    def flagged(p: pd.Period) -> bool:
        return bool(p in review_all.index and (review_all[p] is True or review_all[p] == True))  # noqa: E712

    cur_rev = at(rev_all, latest)
    for key, base, label in (("revenue_mom_pct", prev_m, "previous month"),
                             ("revenue_yoy_pct", prev_y, "same month last year")):
        v = pct_change(cur_rev, at(rev_all, base))
        metrics[key] = metric(
            v, "percent", period=f"{base}/{latest}",
            formula=f"(revenue {latest} - revenue {label}) / revenue {label} * 100",
            reason=f"no valid revenue for {latest} or for the comparison month ({base})",
            note="one of the two months is flagged for review; treat with caution"
            if flagged(latest) or flagged(base) else None)
    # expense changes only when the expense list is complete for both months
    def exp_ok(p: pd.Period) -> float | None:
        return at(exp_all, p) if flag_all.get(p) is True or flag_all.get(p) == True else None  # noqa: E712

    cur_e = exp_ok(latest)
    for key, base, label in (("expenses_mom_pct", prev_m, "previous month"),
                             ("expenses_yoy_pct", prev_y, "same month last year")):
        v = pct_change(cur_e, exp_ok(base)) if base in full else None
        metrics[key] = metric(
            v, "percent", period=f"{base}/{latest}",
            formula=f"(expenses {latest} - expenses {label}) / expenses {label} * 100",
            reason="needs a complete expense list and values for both months")

    # --- 12-month vs previous 12-month revenue --------------------------------
    prev_win = pd.period_range(w_first - WINDOW_MONTHS, w_first - 1, freq="M")
    cur_full = len(win) == WINDOW_MONTHS and rev.notna().all()
    prev_vals = rev_all.reindex(prev_win)
    prev_full = prev_vals.notna().all() and w_first - WINDOW_MONTHS >= first
    g = pct_change(rev.sum(), prev_vals.sum()) if cur_full and prev_full else None
    metrics["revenue_12m_growth_pct"] = metric(
        g, "percent", period=f"{prev_win[0]}/{last}",
        formula="(revenue of latest 12 months - revenue of the 12 months before) / the latter * 100",
        reason="needs 24 consecutive months of revenue")

    # --- trends ------------------------------------------------------------------
    # months flagged for review (negative / extreme values) are left out of trend fitting
    flag_win = review_all.loc[win].map(lambda x: x is True or x == True).astype(bool)  # noqa: E712
    trend = {"revenue": summarize_trend(rev.where(~flag_win)),
             "listed_expenses": summarize_trend(exp.where(~flag_win))}
    for key, name in (("revenue_trend_pct_per_month", "revenue"),
                      ("listed_expenses_trend_pct_per_month", "listed_expenses")):
        t = trend[name]
        metrics[key] = metric(
            t["pct_per_month"], "percent_per_month", period=win_label,
            formula="least-squares slope of monthly values / mean * 100 (months flagged for review excluded)",
            reason=t["reason"])

    # --- monthly series for charts -----------------------------------------------
    monthly = []
    for p in full:
        r, e, f = clean_number(rev_all[p]), clean_number(exp_all[p]), flag_all[p]
        row = {"period": str(p), "revenue": r, "expenses": e,
               "expenses_complete": None if f is None or pd.isna(f) else bool(f)}
        row["profit"] = (clean_number(r - e) if (r is not None and e is not None
                                                 and row["expenses_complete"] is True) else None)
        row["needs_review"] = flagged(p)
        row["listed_expenses_exceed_revenue"] = bool(
            r is not None and e is not None and e > r and not row["needs_review"])
        monthly.append(row)

    coverage = {
        "months_with_revenue": int(rev_all.notna().sum()),
        "first_period": str(first), "last_period": str(last),
        "window_first": str(w_first), "window_last": str(last), "window_months": len(win),
        "missing_periods": [str(p) for p in full if pd.isna(rev_all[p])],
        "expenses_complete": complete if paired.any() else None,
    }
    flagged = [str(p) for p in full if review_all[p] is True or review_all[p] == True]  # noqa: E712
    return {"metrics": metrics, "monthly": monthly, "trend": trend, "coverage": coverage,
            "flagged_periods": flagged}
