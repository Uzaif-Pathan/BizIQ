"""Explainable business health score (0-100). NOT a probability of business success.

How it works (documented in the README):

* Eight components, each with a fixed base weight (sum 100). A component is scored 0-100 by
  a documented piecewise-linear curve on one measured indicator, only if that indicator can
  be computed. Unavailable components are listed and their weight is redistributed
  proportionally over the available ones (``weight`` = effective weight, ``base_weight`` = fixed).
* ``basis`` says what a component rests on:
    - ``benchmark``: scored against an industry benchmark passed in by the caller;
    - ``measured``: scored from an outcome measured in the business's own records
      (margin, growth, cost growth, customer retention);
    - ``rule``: scored from a generic rule-of-thumb threshold on a structural indicator
      (volatility, customer / product concentration). These are not industry benchmarks.
* A score is only produced if >= 40 base weight is available AND at least one financial
  outcome component (profitability, growth, cost control) is available. Otherwise
  ``score`` is null with the reason in ``limitations``.
* Each component reports ``effect_points`` = weight/100 * (points - 50): how many points it
  moved the score above (+) or below (-) a neutral 50, so the factors that raised or lowered
  the score are visible.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from ..common import clean_number

MIN_AVAILABLE_WEIGHT = 40
FINANCIAL_OUTCOMES = ("profitability", "growth", "cost_control")
MIN_CUSTOMERS_FOR_CONCENTRATION = 5
MIN_PRODUCTS_FOR_CONCENTRATION = 3
MIN_POINTS_VOLATILITY = 6
RAISES_AT, LOWERS_AT = 65.0, 40.0  # component points thresholds for the direction label
DISCLAIMER = ("This score summarises the available indicators with fixed, documented rules. "
              "It is not a probability of business success.")

BASE_WEIGHTS = {
    "profitability": 25, "growth": 20, "cost_control": 15, "revenue_stability": 10,
    "customer_loyalty": 10, "customer_concentration": 10,
    "product_margin": 5, "product_concentration": 5,
}

# (indicator value, points) vertices; linear in between, flat beyond the ends.
CURVES: dict[str, list[tuple[float, float]]] = {
    "margin": [(-10, 0), (0, 25), (5, 50), (10, 65), (20, 85), (30, 100)],
    "margin_vs_benchmark_pp": [(-15, 0), (-5, 35), (0, 60), (5, 80), (10, 100)],
    "growth": [(-20, 0), (-10, 25), (0, 50), (10, 70), (25, 90), (40, 100)],
    "cost_gap_pp": [(-10, 100), (-5, 85), (0, 65), (5, 40), (10, 20), (20, 0)],  # expense growth - revenue growth
    "volatility_cv": [(10, 100), (20, 80), (30, 55), (50, 25), (80, 0)],
    "repeat_rate": [(0, 0), (25, 40), (50, 75), (75, 100)],
    "retention": [(0, 0), (25, 35), (40, 60), (60, 85), (80, 100)],
    "top_customer_share": [(5, 100), (15, 70), (25, 40), (40, 10), (60, 0)],
    "top_decile_share": [(30, 100), (50, 70), (70, 35), (90, 0)],
    "gross_margin": [(0, 0), (10, 40), (20, 65), (35, 85), (50, 100)],
    "gross_margin_vs_benchmark_pp": [(-15, 0), (-5, 35), (0, 60), (5, 80), (10, 100)],
    "top_product_share": [(25, 100), (40, 70), (60, 35), (80, 0)],
}


def curve(name: str, x: float) -> float:
    """Score 0-100 for indicator value ``x`` on the named piecewise-linear curve."""
    pts = CURVES[name]
    if x <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(pts[-1][1])


def _val(result: dict | None, key: str) -> float | None:
    if not result or not result.get("metrics"):
        return None
    m = result["metrics"].get(key)
    return None if m is None else m.get("value")


def _benchmark(benchmarks: Sequence[dict] | None, metric: str) -> dict | None:
    """First usable benchmark whose ``metric`` matches exactly (caller filtered geography)."""
    for b in benchmarks or []:
        try:
            if b.get("metric") == metric and math.isfinite(float(b["value"])):
                return {"value": float(b["value"]), "source": b.get("source"), "year": b.get("year"),
                        "geography_level": b.get("geography_level")}
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return None


def _comp(name: str, points: float, value: float | None, basis: str, explanation: str,
          metric: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "base_weight": BASE_WEIGHTS[name], "points": clean_number(points, 1),
            "value": clean_number(value), "metric": metric, "basis": basis,
            "explanation": explanation, **extra}


# ---- one function per component: return a component dict, or (None, reason) ----------------
def _profitability(fin, cus, pro, bm):
    m = _val(fin, "profit_margin_pct")
    if m is None:
        return None, "profit margin unavailable (expenses not marked complete, or no expense data)"
    b = _benchmark(bm, "profit_margin_pct")
    if b:
        pts = curve("margin_vs_benchmark_pp", m - b["value"])
        return _comp("profitability", pts, m, "benchmark",
                     f"Profit margin {m:.1f}% vs benchmark {b['value']:.1f}% "
                     f"({b['source']}, {b['year']}, {b['geography_level']}).", "profit_margin_pct",
                     benchmark=b), None
    return _comp("profitability", curve("margin", m), m, "measured",
                 f"Profit margin {m:.1f}% (generic score curve; no benchmark supplied).",
                 "profit_margin_pct"), None


def _growth(fin, cus, pro, bm):
    for key, label in (("revenue_12m_growth_pct", "12-month revenue growth"),
                       ("revenue_yoy_pct", "year-on-year revenue change")):
        g = _val(fin, key)
        if g is not None:
            return _comp("growth", curve("growth", g), g, "measured", f"{label} {g:+.1f}%.", key), None
    t = (fin or {}).get("trend", {}).get("revenue", {}) if fin else {}
    if t.get("pct_per_month") is not None and t.get("direction") in ("increasing", "decreasing", "flat"):
        g = t["pct_per_month"] * 12
        return _comp("growth", curve("growth", g), g, "measured",
                     f"Revenue trend {t['pct_per_month']:+.1f}% per month (about {g:+.0f}% a year, {t['direction']}).",
                     "revenue_trend_pct_per_month"), None
    return None, "no growth figure (needs a year-on-year comparison or a clear revenue trend)"


def _cost_control(fin, cus, pro, bm):
    e, r = _val(fin, "expenses_yoy_pct"), _val(fin, "revenue_yoy_pct")
    if e is None or r is None:
        return None, "needs year-on-year change for both revenue and expenses"
    gap = e - r
    return _comp("cost_control", curve("cost_gap_pp", gap), gap, "measured",
                 f"Expenses changed {e:+.1f}% vs revenue {r:+.1f}% year on year "
                 f"(gap {gap:+.1f} percentage points).", "expenses_yoy_pct - revenue_yoy_pct"), None


def _stability(fin, cus, pro, bm):
    vals = [r["revenue"] for r in (fin or {}).get("monthly", []) if r.get("revenue") is not None]
    if len(vals) < MIN_POINTS_VOLATILITY:
        return None, f"needs at least {MIN_POINTS_VOLATILITY} months of revenue to judge stability"
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return None, "average revenue is not positive"
    sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    cv = sd / mean * 100
    return _comp("revenue_stability", curve("volatility_cv", cv), cv, "rule",
                 f"Monthly revenue varies by {cv:.0f}% around its average (lower is steadier).",
                 "revenue_volatility_cv_pct"), None


def _loyalty(fin, cus, pro, bm):
    rep, ret = _val(cus, "repeat_customer_rate_pct"), _val(cus, "avg_monthly_retention_pct")
    parts = []
    if rep is not None:
        parts.append(curve("repeat_rate", rep))
    if ret is not None:
        parts.append(curve("retention", ret))
    if not parts:
        return None, "no repeat-customer or retention figure"
    bits = ([f"{rep:.0f}% repeat customers"] if rep is not None else []) + \
           ([f"{ret:.0f}% monthly retention"] if ret is not None else [])
    return _comp("customer_loyalty", sum(parts) / len(parts), rep if rep is not None else ret, "measured",
                 ", ".join(bits).capitalize() + ".",
                 "repeat_customer_rate_pct" if rep is not None else "avg_monthly_retention_pct"), None


def _cust_conc(fin, cus, pro, bm):
    n = (_val(cus, "active_customers") or 0)
    top1, top10 = _val(cus, "top_customer_share_pct"), _val(cus, "top_10pct_customers_share_pct")
    if top1 is None or n < MIN_CUSTOMERS_FOR_CONCENTRATION:
        return None, f"needs at least {MIN_CUSTOMERS_FOR_CONCENTRATION} customers to judge concentration"
    parts = [curve("top_customer_share", top1)] + ([curve("top_decile_share", top10)] if top10 is not None else [])
    txt = f"Largest customer {top1:.0f}% of spend" + (f", top 10% of customers {top10:.0f}%" if top10 is not None else "")
    return _comp("customer_concentration", min(parts), top1, "rule", txt + " (lower is safer).",
                 "top_customer_share_pct"), None


def _prod_margin(fin, cus, pro, bm):
    gm = _val(pro, "gross_margin_pct")
    if gm is None:
        return None, "gross margin unavailable (needs product cost data)"
    neg = int(_val(pro, "products_with_negative_margin") or 0)
    b = _benchmark(bm, "gross_margin_pct")
    if b:
        pts, basis = curve("gross_margin_vs_benchmark_pp", gm - b["value"]), "benchmark"
        txt = f"Gross margin {gm:.1f}% vs benchmark {b['value']:.1f}% ({b['source']}, {b['year']}, {b['geography_level']})"
        extra = {"benchmark": b}
    else:
        pts, basis, txt, extra = curve("gross_margin", gm), "measured", f"Gross margin {gm:.1f}%", {}
    if neg:
        pts = max(0.0, pts - min(20, 10 * neg))
        txt += f"; {neg} product(s) sell below cost"
    return _comp("product_margin", pts, gm, basis, txt + ".", "gross_margin_pct", **extra), None


def _prod_conc(fin, cus, pro, bm):
    n, top = (_val(pro, "product_count") or 0), _val(pro, "top_product_share_pct")
    if top is None or n < MIN_PRODUCTS_FOR_CONCENTRATION:
        return None, f"needs at least {MIN_PRODUCTS_FOR_CONCENTRATION} products to judge concentration"
    return _comp("product_concentration", curve("top_product_share", top), top, "rule",
                 f"Best-selling product is {top:.0f}% of product revenue (lower is safer).",
                 "top_product_share_pct"), None


_BUILDERS = (_profitability, _growth, _cost_control, _stability, _loyalty, _cust_conc, _prod_margin, _prod_conc)


def compute_health_score(fin: dict | None, cus: dict | None = None, pro: dict | None = None,
                         benchmarks: Sequence[dict] | None = None) -> dict[str, Any]:
    """Health score from the ``analyze_financials`` / ``analyze_customers`` / ``analyze_products``
    results (any may be ``None``). Never raises; returns the contract ``health_score`` object."""
    try:
        return _compute(fin, cus, pro, benchmarks)
    except Exception as exc:  # noqa: BLE001
        return {"score": None, "band": None, "components": [], "unavailable_components": list(BASE_WEIGHTS),
                "limitations": [f"Score could not be computed: {type(exc).__name__}: {exc}"],
                "disclaimer": DISCLAIMER}


def _compute(fin, cus, pro, benchmarks) -> dict[str, Any]:
    comps, unavailable, limitations = [], [], []
    for build in _BUILDERS:
        c, reason = build(fin, cus, pro, benchmarks)
        if c is None:
            unavailable.append(_NAME_FOR[build])
            limitations.append(f"{_NAME_FOR[build]}: {reason}.")
        else:
            comps.append(c)

    avail = sum(c["base_weight"] for c in comps)
    has_outcome = any(c["name"] in FINANCIAL_OUTCOMES for c in comps)
    if avail < MIN_AVAILABLE_WEIGHT or not has_outcome:
        limitations.insert(0, "Not enough data for a score: it needs at least one financial outcome "
                              "(profitability, growth or cost control) and indicators covering at least "
                              f"{MIN_AVAILABLE_WEIGHT}% of the scoring weight (have {avail}%).")
        for c in comps:
            c.update(weight=None, direction=None, effect_points=None)
        return {"score": None, "band": None, "components": comps, "unavailable_components": unavailable,
                "limitations": limitations, "coverage_pct": avail, "disclaimer": DISCLAIMER}

    score = 0.0
    for c in comps:
        c["weight"] = clean_number(c["base_weight"] / avail * 100, 1)
        c["effect_points"] = clean_number(c["weight"] / 100 * (c["points"] - 50), 1)
        c["direction"] = "raises" if c["points"] >= RAISES_AT else "lowers" if c["points"] <= LOWERS_AT else "neutral"
        score += c["weight"] / 100 * c["points"]
    comps.sort(key=lambda c: -abs(c["effect_points"]))
    score = round(max(0.0, min(100.0, score)), 1)
    if avail < 100:
        limitations.append(f"Score based on indicators covering {avail}% of the full scoring weight; "
                           "the rest was redistributed over the available indicators.")
    if not any(c["basis"] == "benchmark" for c in comps):
        limitations.append("No industry benchmark was used; components rest on the business's own figures "
                           "and generic rules of thumb.")
    return {"score": score, "band": _band(score), "components": comps,
            "unavailable_components": unavailable, "limitations": limitations,
            "coverage_pct": avail,
            "raised_by": [c["name"] for c in comps if c["direction"] == "raises"][:3],
            "lowered_by": [c["name"] for c in comps if c["direction"] == "lowers"][:3],
            "disclaimer": DISCLAIMER}


def _band(score: float) -> str:
    return "strong" if score >= 75 else "moderate" if score >= 55 else "weak" if score >= 35 else "at risk"


_NAME_FOR = ({_profitability: "profitability", _growth: "growth", _cost_control: "cost_control",
                  _stability: "revenue_stability", _loyalty: "customer_loyalty",
                  _cust_conc: "customer_concentration", _prod_margin: "product_margin",
                  _prod_conc: "product_concentration"})
