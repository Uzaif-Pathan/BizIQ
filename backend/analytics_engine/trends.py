"""Shared trend and reporting-window logic (used by financial, customer and product modules)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .common import clean_number, linear_trend

WINDOW_MONTHS = 12  # reporting window: latest 12 calendar months
MIN_TREND_POINTS = 6
TREND_FLAT_BAND_PCT = 0.5  # |slope| below this % of the mean per month counts as "flat"
TREND_MIN_R2 = 0.3  # a line explaining less than this share of variance is "unclear"


def latest_window(first: pd.Period, last: pd.Period) -> pd.PeriodIndex:
    """Calendar months of the reporting window: up to 12 months ending at ``last``."""
    return pd.period_range(max(first, last - (WINDOW_MONTHS - 1)), last, freq="M")


def direction(pct_per_month: float | None, r2: float | None) -> str | None:
    if pct_per_month is None:
        return None
    if r2 is None or r2 < TREND_MIN_R2:
        return "unclear"  # swings (e.g. seasonality) dominate; no reliable up/down call
    if pct_per_month > TREND_FLAT_BAND_PCT:
        return "increasing"
    if pct_per_month < -TREND_FLAT_BAND_PCT:
        return "decreasing"
    return "flat"


def summarize_trend(series: pd.Series, min_points: int = MIN_TREND_POINTS) -> dict[str, Any]:
    """Trend of a monthly series indexed by a monthly PeriodIndex (NaN months are skipped).

    Returns ``pct_per_month`` (slope / mean * 100), ``slope`` (units of the series per
    month), ``direction`` (increasing / decreasing / flat / unclear), ``r2``, ``n_points``
    and ``reason`` (set when the trend could not be computed).
    """
    pts = series.dropna()
    base = {"pct_per_month": None, "slope": None, "direction": None, "r2": None,
            "n_points": int(len(pts)), "reason": None}
    if len(pts) < min_points:
        return {**base, "reason": f"needs at least {min_points} monthly values (have {len(pts)})"}
    pos = [(p - pts.index[0]).n for p in pts.index]
    t = linear_trend([float(v) for v in pts.to_numpy()], pos)
    if t is None:
        return {**base, "reason": "trend cannot be computed (non-positive average)"}
    pct, r2 = clean_number(t["pct_per_step"]), clean_number(t["r2"], 3)
    return {**base, "pct_per_month": pct, "slope": clean_number(t["slope"], 4),
            "direction": direction(pct, r2), "r2": r2}
