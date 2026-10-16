"""Findings from product metrics (generic rules of thumb, documented in the README)."""

from __future__ import annotations

from typing import Any

TOP_PRODUCT_MEDIUM, TOP_PRODUCT_HIGH = 40.0, 60.0
LOW_MARGIN = 10.0  # gross margin % below this is thin
BIG_SELLER_SHARE = 15.0  # share % from which a product counts as a main seller
SMALL_CONTRIB = 5.0  # share % below which a product contributes little
MIN_SHARE_SLOPE_PP = 0.1  # share must move by at least this many pp per month to be reported
MAX_MOVERS = 3
COVERAGE_LOW = 50.0


def _v(m, k):
    x = m.get(k)
    return None if x is None else x.get("value")


def _f(id_, type_, metric, value, evidence, severity, comparison=None):
    return {"id": id_, "type": type_, "metric": metric, "value": value,
            "comparison": comparison, "evidence": evidence, "severity": severity}


def build_product_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result.get("available"):
        return []
    m, rows = result["metrics"], result["products"]
    n = len(rows)
    out: list[dict[str, Any]] = []

    top = _v(m, "top_product_share_pct")
    if top is not None and n >= 2:
        sev = "high" if top >= TOP_PRODUCT_HIGH else "medium" if top >= TOP_PRODUCT_MEDIUM else "info"
        out.append(_f("PRD-CONC", "product_concentration", "top_product_share_pct", top,
                      f"'{rows[0]['product_name']}' brings {top:.0f}% of product revenue"
                      + (f"; the top 3 bring {_v(m, 'top_3_products_share_pct'):.0f}%."
                         if _v(m, "top_3_products_share_pct") is not None else "."), sev,
                      comparison=f"generic rule of thumb: one product >= {TOP_PRODUCT_MEDIUM:.0f}% "
                                 "of revenue is a dependency"))

    for r in rows:
        mg, share = r["gross_margin_pct"], r["revenue_share_pct"] or 0
        if mg is None:
            continue
        if mg < 0:
            out.append(_f(f"PRD-NEGMARGIN-{r['product_id']}", "negative_margin_product",
                          "gross_margin_pct", mg,
                          f"'{r['product_name']}' costs more than it earns (gross margin "
                          f"{mg:.1f}%, {share:.0f}% of product revenue).", "high"))
        elif mg < LOW_MARGIN and share >= BIG_SELLER_SHARE:
            out.append(_f(f"PRD-LOWMARGIN-{r['product_id']}", "low_margin_main_product",
                          "gross_margin_pct", mg,
                          f"'{r['product_name']}' is a main seller ({share:.0f}% of product "
                          f"revenue) but earns only {mg:.1f}% gross margin.", "medium",
                          comparison=f"generic rule of thumb: below {LOW_MARGIN:.0f}% is thin"))

    # movers: absolute decline first, otherwise share loss; share gains are informational
    decl, loss, gain = [], [], []
    for r in rows:
        rt, st = r["revenue_trend"], r["share_trend"]
        if rt["direction"] == "decreasing":
            decl.append((rt["pct_per_month"], r))
        elif st["direction"] == "decreasing" and st["slope"] is not None \
                and st["slope"] <= -MIN_SHARE_SLOPE_PP:
            loss.append((st["slope"], r))
        elif st["direction"] == "increasing" and st["slope"] is not None \
                and st["slope"] >= MIN_SHARE_SLOPE_PP:
            gain.append((st["slope"], r))
    for val, r in sorted(decl, key=lambda x: x[0])[:MAX_MOVERS]:
        share = r["revenue_share_pct"] or 0
        out.append(_f(f"PRD-DECLINE-{r['product_id']}", "product_revenue_declining",
                      "revenue_trend_pct_per_month", val,
                      f"Revenue of '{r['product_name']}' is falling ({val:+.1f}% per month, "
                      f"fit R² {r['revenue_trend']['r2']}); it is {share:.0f}% of product revenue.",
                      "medium" if share >= 10 else "low"))
    for val, r in sorted(loss, key=lambda x: x[0])[:MAX_MOVERS]:
        share = r["revenue_share_pct"] or 0
        out.append(_f(f"PRD-SHARELOSS-{r['product_id']}", "product_losing_share",
                      "share_trend_pp_per_month", val,
                      f"'{r['product_name']}' is losing share of revenue ({val:+.2f} percentage "
                      f"points per month; now {share:.0f}% on average).",
                      "medium" if share >= 10 else "low"))
    for val, r in sorted(gain, key=lambda x: -x[0])[:MAX_MOVERS]:
        out.append(_f(f"PRD-GAINING-{r['product_id']}", "product_gaining_share",
                      "share_trend_pp_per_month", val,
                      f"'{r['product_name']}' is gaining share of revenue ({val:+.2f} percentage "
                      "points per month).", "info"))

    small = [r for r in rows if (r["revenue_share_pct"] or 0) < SMALL_CONTRIB]
    if n >= 5 and len(small) >= 2:
        names = ", ".join(f"'{r['product_name']}'" for r in small[-3:])
        out.append(_f("PRD-LOWCONTRIB", "low_contribution_products", "products_below_5pct_share",
                      float(len(small)),
                      f"{len(small)} of {n} products each bring under {SMALL_CONTRIB:.0f}% of "
                      f"product revenue (smallest: {names}).", "low"))

    cov = _v(m, "product_data_coverage_pct")
    if cov is not None and cov < COVERAGE_LOW:
        out.append(_f("PRD-COVERAGE", "product_data_coverage_low", "product_data_coverage_pct", cov,
                      f"Product records account for only {cov:.0f}% of reported revenue, so product "
                      "insights describe only part of the business.", "low"))
    return out
