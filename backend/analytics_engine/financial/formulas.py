"""Pure formula functions for financial analysis (no DataFrames, easy to test).

All formulas are documented in docs/ENGINE_FORMULAS.md.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..common import to_float

# --- trend classification thresholds (documented in docs/ENGINE_FORMULAS.md) ---------
MIN_TREND_POINTS = 4          # fewer monthly observations -> no trend is reported
FLAT_THRESHOLD_PCT = 0.5      # |slope| below 0.5% of the mean per month counts as flat
MIN_TREND_R2 = 0.25           # weaker linear fit than this is reported as "unclear"
MIN_CV_POINTS = 3             # observations needed for volatility


def safe_div(numerator, denominator) -> float | None:
    """numerator / denominator, or ``None`` if either is missing or the denominator is 0."""
    n, d = to_float(numerator), to_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return n / d


def pct_of(part, whole) -> tuple[float | None, str | None]:
    """part / whole * 100, only when whole > 0. Returns (value, reason_if_none)."""
    p, w = to_float(part), to_float(whole)
    if p is None or w is None:
        return None, "A required value is missing."
    if w <= 0:
        return None, "The denominator is zero or negative, so the ratio is undefined."
    return p / w * 100.0, None


def pct_change(new, old) -> tuple[float | None, str | None]:
    """Percent change from ``old`` to ``new``: (new - old) / old * 100.

    Only defined when both values exist and ``old`` > 0. Returns (value, reason_if_none).
    """
    n, o = to_float(new), to_float(old)
    if n is None or o is None:
        return None, "The comparison period has no value."
    if o <= 0:
        return None, "The earlier value is zero or negative, so a percent change is undefined."
    return (n - o) / o * 100.0, None


def linear_trend(x: Sequence[float], y: Sequence[float]) -> dict | None:
    """Ordinary least-squares line through (x, y).

    Returns ``{"slope", "intercept", "r2", "n"}`` or ``None`` if fewer than 2 points or x is
    constant. When y is constant the fit is perfect, so r2 is reported as 1.0.
    """
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    if len(xs) < 2 or np.ptp(xs) == 0:
        return None
    slope, intercept = np.polyfit(xs, ys, 1)
    ss_tot = float(np.sum((ys - ys.mean()) ** 2))
    ss_res = float(np.sum((ys - (slope * xs + intercept)) ** 2))
    r2 = 1.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot)
    return {"slope": float(slope), "intercept": float(intercept), "r2": float(r2), "n": int(len(xs))}


def classify_trend(slope_pct_per_month: float, r2: float) -> str:
    """'flat' | 'unclear' | 'increasing' | 'decreasing' (see thresholds above)."""
    if abs(slope_pct_per_month) < FLAT_THRESHOLD_PCT:
        return "flat"
    if r2 < MIN_TREND_R2:
        return "unclear"
    return "increasing" if slope_pct_per_month > 0 else "decreasing"


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    """Sample standard deviation / mean * 100. ``None`` with < 3 values or non-positive mean."""
    vals = np.asarray([v for v in (to_float(v) for v in values) if v is not None], dtype=float)
    if len(vals) < MIN_CV_POINTS:
        return None
    mean = float(vals.mean())
    if mean <= 0:
        return None
    return float(vals.std(ddof=1)) / mean * 100.0
