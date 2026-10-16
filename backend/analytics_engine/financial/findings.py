"""Turn financial metrics into findings (each finding is backed by a computed metric).

Thresholds are generic rules of thumb, not industry benchmarks; findings that rely on
them say so in ``comparison``. Benchmark-based comparison is added separately
(``scoring``/benchmarks) and only when Person 3 supplies a matching benchmark.
"""

from __future__ import annotations

from typing import Any

# Rule thresholds (percent) -- documented in the README.
MARGIN_LOSS = 0.0
MARGIN_THIN = 5.0
MARGIN_MODERATE = 10.0
YOY_DECLINE = -10.0
MOM_DROP = -15.0
EXPENSE_OUTPACE_PP = 0.5  # expenses trend minus revenue trend, percentage points per month
VOLATILITY_CV = 0.25
MIN_POINTS_VOLATILITY = 6
TREND_FLAT_LIMIT = 0.5  # |revenue trend| below this %/month is not worth a warning


def _v(metrics: dict, key: str) -> float | None:
    m = metrics.get(key)
    return None if m is None else m.get("value")


def _f(id_: str, type_: str, metric: str, value: float | None, evidence: str, severity: str,
       comparison: str | None = None) -> dict[str, Any]:
    return {"id": id_, "type": type_, "metric": metric, "value": value,
            "comparison": comparison, "evidence": evidence, "severity": severity}


def build_financial_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    """``result`` is the dict returned by ``analyze_financials``."""
    m, trend, cov = result["metrics"], result["trend"], result["coverage"]
    if not m:
        return []
    out: list[dict[str, Any]] = []
    period = m["revenue"]["period"]

    # profit margin level -------------------------------------------------------
    margin = _v(m, "profit_margin_pct")
    if margin is not None:
        if margin < MARGIN_LOSS:
            sev, what = "high", "the business made a loss over the period"
        elif margin < MARGIN_THIN:
            sev, what = "medium", "profit margin is thin"
        elif margin < MARGIN_MODERATE:
            sev, what = "low", "profit margin is modest"
        else:
            sev, what = "info", "profit margin is healthy by the generic rule of thumb"
        out.append(_f("FIN-MARGIN", "profit_margin_level", "profit_margin_pct", margin,
                      f"Profit margin was {margin:.1f}% over {period}: {what}.", sev,
                      comparison=f"generic rule of thumb: <{MARGIN_LOSS:.0f}% loss, "
                                 f"<{MARGIN_THIN:.0f}% thin, <{MARGIN_MODERATE:.0f}% modest "
                                 "(not an industry benchmark)"))
    else:
        rmle = _v(m, "revenue_minus_listed_expenses")
        if rmle is not None:
            out.append(_f("FIN-EXPDEF", "expense_definition_incomplete",
                          "revenue_minus_listed_expenses", rmle,
                          f"Profit cannot be computed: {m['profit'].get('reason')}. Revenue minus "
                          f"the expenses that were listed is INR {rmle:,.0f} over {period}; real "
                          "profit is lower if unlisted costs exist.", "medium"))

    # listed expenses above revenue (valid evidence of loss even if list incomplete) -------
    loss_months = [r["period"] for r in result["monthly"] if r["listed_expenses_exceed_revenue"]]
    if loss_months:
        sev = "high" if len(loss_months) >= 3 else "medium"
        out.append(_f("FIN-LOSSMONTHS", "loss_months", "months_with_listed_expenses_above_revenue",
                      float(len(loss_months)),
                      f"Listed expenses were higher than revenue in {len(loss_months)} month(s): "
                      f"{', '.join(loss_months[:6])}{'...' if len(loss_months) > 6 else ''}.", sev))

    # revenue trend --------------------------------------------------------------------
    rt = trend["revenue"]
    if rt["pct_per_month"] is not None:
        d, p = rt["direction"], rt["pct_per_month"]
        if d == "unclear":
            out.append(_f("FIN-REVTREND", "revenue_trend_unclear", "revenue_trend_pct_per_month", p,
                          f"Monthly revenue has no consistent up or down pattern over {period} "
                          f"(straight-line fit R² {rt['r2']}); month-to-month swings dominate.",
                          "info"))
        else:
            sev = "high" if p < -2 else "medium" if p < -TREND_FLAT_LIMIT else "info"
            out.append(_f("FIN-REVTREND", f"revenue_trend_{d}", "revenue_trend_pct_per_month", p,
                          f"Revenue trend is {d} ({p:+.2f}% per month on average over {period}, "
                          f"fit R² {rt['r2']}). Seasonal swings can make short trends unreliable.",
                          sev))

    # latest-month moves ----------------------------------------------------------------
    yoy, mom = _v(m, "revenue_yoy_pct"), _v(m, "revenue_mom_pct")
    if yoy is not None and yoy <= YOY_DECLINE:
        out.append(_f("FIN-YOYDROP", "revenue_decline_yoy", "revenue_yoy_pct", yoy,
                      f"Revenue in {cov['last_period']} is {abs(yoy):.1f}% lower than the same "
                      "month last year.", "medium" if yoy > -25 else "high"))
    if mom is not None and mom <= MOM_DROP:
        out.append(_f("FIN-MOMDROP", "revenue_decline_mom", "revenue_mom_pct", mom,
                      f"Revenue in {cov['last_period']} fell {abs(mom):.1f}% from the previous "
                      "month (single-month moves can be seasonal).", "low"))
    g12 = _v(m, "revenue_12m_growth_pct")
    if g12 is not None:
        out.append(_f("FIN-GROWTH12", "revenue_growth_12m", "revenue_12m_growth_pct", g12,
                      f"Revenue over the latest 12 months is {g12:+.1f}% versus the 12 months "
                      "before.", "medium" if g12 <= YOY_DECLINE else "info"))

    # costs growing faster than sales -----------------------------------------------------
    et = trend["listed_expenses"]
    if (rt["pct_per_month"] is not None and et["pct_per_month"] is not None
            and rt["direction"] != "unclear" and et["direction"] != "unclear"):
        gap = et["pct_per_month"] - rt["pct_per_month"]
        if gap > EXPENSE_OUTPACE_PP:
            out.append(_f("FIN-COSTOUTPACE", "expenses_outpacing_revenue",
                          "listed_expenses_trend_pct_per_month", et["pct_per_month"],
                          f"Listed expenses trend {et['pct_per_month']:+.2f}%/month versus revenue "
                          f"{rt['pct_per_month']:+.2f}%/month: costs are growing "
                          f"{gap:.2f} percentage points per month faster than sales.",
                          "medium" if gap < 2 else "high",
                          comparison="expense trend minus revenue trend"))

    # volatility -----------------------------------------------------------------------------
    series = [r["revenue"] for r in result["monthly"][-12:]
              if r["revenue"] is not None and not r["needs_review"]]
    if len(series) >= MIN_POINTS_VOLATILITY:
        mean = sum(series) / len(series)
        if mean > 0:
            sd = (sum((x - mean) ** 2 for x in series) / (len(series) - 1)) ** 0.5
            cv = sd / mean
            if cv >= VOLATILITY_CV:
                out.append(_f("FIN-VOLATILE", "revenue_volatility", "revenue_cv", round(cv, 3),
                              f"Monthly revenue varies a lot (std/mean = {cv:.2f}), which makes "
                              "cash planning harder.", "low"))

    # data needing review ------------------------------------------------------------------------
    if result["flagged_periods"]:
        fp = result["flagged_periods"]
        out.append(_f("FIN-REVIEW", "data_needs_review", "flagged_months", float(len(fp)),
                      f"{len(fp)} month(s) contain unusual values (negative or extreme) that were "
                      f"kept but flagged: {', '.join(fp[:6])}. Metrics may be distorted until "
                      "these are checked.", "medium"))
    return out
