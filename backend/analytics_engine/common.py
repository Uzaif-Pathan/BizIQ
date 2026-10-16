"""Small helpers shared by every analytics module.

Conventions (see contracts/analysis-result.schema.json):
* money is a plain INR number, months are ``YYYY-MM``, percentages are percent numbers
* a value that cannot be computed is ``None`` (JSON ``null``) -- never 0 -- and the
  metric carries a ``reason`` explaining why.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def clean_number(x: Any, ndigits: int = 2) -> float | None:
    """Return a rounded Python float, or None for None/NaN/inf (JSON-safe)."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, ndigits)


def metric(value: Any, unit: str, *, period: str | None = None, formula: str = "",
           reason: str | None = None, note: str | None = None, ndigits: int = 2) -> dict[str, Any]:
    """Build one metric object for the result JSON.

    ``reason`` is only meaningful (and only kept) when ``value`` is None.
    ``note`` is an optional caveat for a value that *was* computed.
    """
    v = clean_number(value, ndigits)
    out: dict[str, Any] = {"value": v, "unit": unit, "period": period, "formula": formula}
    if v is None:
        out["reason"] = reason or "not available"
    elif note:
        out["note"] = note
    return out


def pct_change(new: Any, old: Any) -> float | None:
    """Percent change from ``old`` to ``new``.

    None if either value is missing or ``old`` is not strictly positive (a change from
    zero or from a negative base has no meaningful percentage).
    """
    n, o = clean_number(new, 10), clean_number(old, 10)
    if n is None or o is None or o <= 0:
        return None
    return (n - o) / o * 100.0


def safe_ratio_pct(numerator: Any, denominator: Any) -> float | None:
    """``numerator / denominator * 100``, only when the denominator is > 0."""
    n, d = clean_number(numerator, 10), clean_number(denominator, 10)
    if n is None or d is None or d <= 0:
        return None
    return n / d * 100.0


def linear_trend(values: list[float], positions: list[float] | None = None) -> dict[str, Any] | None:
    """Least-squares line through ``values``.

    ``positions`` are the x coordinates (e.g. month offsets, so calendar gaps are
    respected); default is 0, 1, 2, ... Returns slope, slope as a % of the mean per
    step, and R^2; None if fewer than 2 points or a zero/negative mean (a percent
    slope would be meaningless).
    """
    y = np.asarray(values, dtype=float)
    if len(y) < 2 or not np.isfinite(y).all():
        return None
    x = np.arange(len(y), dtype=float) if positions is None else np.asarray(positions, dtype=float)
    if len(x) != len(y) or np.ptp(x) == 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    mean = float(y.mean())
    if mean <= 0:
        return None
    fitted = slope * x + intercept
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - mean) ** 2).sum())
    # a constant series is fitted exactly by a flat line (R^2 = 1), not "unexplained"
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"slope": float(slope), "pct_per_step": float(slope) / mean * 100.0, "r2": r2}
