"""Findings from customer metrics. Thresholds are generic rules of thumb (documented in the
README), not industry benchmarks."""

from __future__ import annotations

from typing import Any

REPEAT_LOW = 25.0  # % of customers buying in 2+ months below which repeat business is weak
RETENTION_HIGH_RISK = 25.0
RETENTION_LOW = 40.0
TOP1_HIGH, TOP1_MEDIUM = 25.0, 15.0
TOP10PCT_HIGH, TOP10PCT_MEDIUM = 70.0, 50.0
TOP5_MEDIUM = 60.0
COVERAGE_LOW = 50.0
MIN_CUSTOMERS_TOP1 = 5
MIN_CUSTOMERS_TOP5 = 10


def _v(m: dict, key: str) -> float | None:
    x = m.get(key)
    return None if x is None else x.get("value")


def _f(id_, type_, metric, value, evidence, severity, comparison=None):
    return {"id": id_, "type": type_, "metric": metric, "value": value,
            "comparison": comparison, "evidence": evidence, "severity": severity}


def build_customer_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result.get("available"):
        return []
    m, trend, n = result["metrics"], result["trend"], result["coverage"]["customers"]
    out: list[dict[str, Any]] = []

    rep = _v(m, "repeat_customer_rate_pct")
    if rep is not None:
        weak = rep < REPEAT_LOW
        out.append(_f("CUS-REPEAT", "repeat_customers_low" if weak else "repeat_customers",
                      "repeat_customer_rate_pct", rep,
                      f"{rep:.0f}% of customers bought in two or more different months "
                      f"({'weak' if weak else 'acceptable'} repeat business by the generic rule).",
                      "medium" if weak else "info",
                      comparison=f"generic rule of thumb: below {REPEAT_LOW:.0f}% is weak "
                                 "(not an industry benchmark)"))

    ret = _v(m, "avg_monthly_retention_pct")
    if ret is not None:
        sev = "high" if ret < RETENTION_HIGH_RISK else "medium" if ret < RETENTION_LOW else "info"
        out.append(_f("CUS-RETENTION", "customer_retention_low" if sev != "info" else "customer_retention",
                      "avg_monthly_retention_pct", ret,
                      f"On average {ret:.0f}% of a month's customers came back the next month.",
                      sev, comparison=f"generic rule of thumb: below {RETENTION_LOW:.0f}% is low"))

    top1, top5, top10 = (_v(m, "top_customer_share_pct"), _v(m, "top_5_customers_share_pct"),
                         _v(m, "top_10pct_customers_share_pct"))
    if top1 is not None and n >= MIN_CUSTOMERS_TOP1:
        high = top1 >= TOP1_HIGH or (top10 is not None and top10 >= TOP10PCT_HIGH)
        med = (top1 >= TOP1_MEDIUM or (top10 is not None and top10 >= TOP10PCT_MEDIUM)
               or (top5 is not None and n >= MIN_CUSTOMERS_TOP5 and top5 >= TOP5_MEDIUM))
        parts = [f"largest customer {top1:.0f}% of spend"]
        if top5 is not None and n >= MIN_CUSTOMERS_TOP5:
            parts.append(f"top 5 customers {top5:.0f}%")
        if top10 is not None:
            parts.append(f"top 10% of customers {top10:.0f}%")
        out.append(_f("CUS-CONC", "customer_concentration", "top_customer_share_pct", top1,
                      "Spend concentration: " + ", ".join(parts) + f" ({n} customers).",
                      "high" if high else "medium" if med else "info",
                      comparison=f"generic rule of thumb: largest customer >= {TOP1_MEDIUM:.0f}% "
                                 f"or top 10% >= {TOP10PCT_MEDIUM:.0f}% signals dependence"))

    t = trend["active_customers"]
    if t["direction"] in ("increasing", "decreasing"):
        p = t["pct_per_month"]
        out.append(_f("CUS-TREND", f"active_customers_{t['direction']}",
                      "active_customers_trend_pct_per_month", p,
                      f"Monthly active customers are {t['direction']} ({p:+.1f}% per month, "
                      f"fit R² {t['r2']}).", "medium" if t["direction"] == "decreasing" else "info"))

    cov = _v(m, "customer_data_coverage_pct")
    if cov is not None and cov < COVERAGE_LOW:
        out.append(_f("CUS-COVERAGE", "customer_data_coverage_low", "customer_data_coverage_pct",
                      cov, f"Customer records account for only {cov:.0f}% of reported revenue, "
                      "so customer insights describe only part of the business.", "low"))

    if result["coverage"].get("rows_flagged_for_review"):
        k = result["coverage"]["rows_flagged_for_review"]
        out.append(_f("CUS-REVIEW", "data_needs_review", "customer_rows_flagged", float(k),
                      f"{k} customer row(s) have unusual values (e.g. negative) and were flagged "
                      "for review.", "low"))
    return out
