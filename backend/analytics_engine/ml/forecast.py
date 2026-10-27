"""Short-term revenue forecast, evaluated on held-out history before it is shown.

Method (documented in the README):

* Series: monthly revenue from the validated financials. Missing months stay missing --
  they are never filled or set to 0. Models use the calendar month as x, so gaps are respected.
* Eligibility: >= 9 months with revenue (>= 6 to train + 3 held out) and a positive mean.
* Candidates: ``naive`` (repeat the last value), ``moving_average_3`` (mean of the last 3
  months) and ``linear`` (least-squares line on the calendar month).
* Evaluation: time-ordered holdout -- the last 3 observed months are hidden, each candidate is
  fitted on the earlier months and scored on them (MAE, RMSE, MAPE). The lowest MAE wins;
  ties go to the simpler model (naive < moving_average_3 < linear).
* Reliability gate: the forecast is only returned if the winner's holdout MAPE <= 25 %.
  Otherwise status is ``skipped_insufficient_data`` (``skip_code = "poor_accuracy"``) and the
  evaluation is still reported, but no future values are shown.
* Forecast: the winner is refitted on all months and projected 3 months ahead. The
  ``low``/``high`` band is forecast -/+ the holdout RMSE (a typical error, NOT a statistical
  confidence interval), clamped at 0.
* ``beats_naive`` tells whether the winner has a lower holdout MAE than repeating the last value.

The function never raises: any failure is returned as ``status: "failed"``.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from ..common import clean_number

MIN_OBSERVATIONS = 9
HOLDOUT_MONTHS = 3
MIN_TRAIN_MONTHS = 6
HORIZON_MONTHS = 3
MAX_MAPE_PCT = 25.0


def _naive(x, y, xp):
    return np.full(len(xp), y[-1], dtype=float)


def _ma3(x, y, xp):
    return np.full(len(xp), float(np.mean(y[-3:])), dtype=float)


def _linear(x, y, xp):
    slope, intercept = np.polyfit(x, y, 1)
    return slope * np.asarray(xp, dtype=float) + intercept


CANDIDATES: dict[str, Callable] = {"naive": _naive, "moving_average_3": _ma3, "linear": _linear}


def _model(status: str, reason: str | None = None, **details: Any) -> dict[str, Any]:
    d = {k: v for k, v in details.items() if v is not None}
    if reason:
        d["reason"] = reason
    return {"status": status, "mae": None, "rmse": None, "details": d}


def _scores(actual: np.ndarray, pred: np.ndarray) -> dict[str, float | None]:
    err = actual - pred
    mape = float(np.mean(np.abs(err) / actual) * 100) if (actual > 0).all() else None
    return {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))), "mape_pct": mape}


def forecast_revenue(clean: pd.DataFrame | None, horizon: int = HORIZON_MONTHS) -> dict[str, Any]:
    """Revenue forecast. Returns the contract ``model`` object (mae/rmse = holdout scores)."""
    try:
        return _forecast(clean, max(1, min(int(horizon), 6)))
    except Exception as exc:  # noqa: BLE001 - the engine must never raise on a model failure
        return _model("failed", f"Forecast failed: {type(exc).__name__}: {exc}")


def _forecast(clean: pd.DataFrame | None, horizon: int) -> dict[str, Any]:
    if clean is None or len(clean) == 0 or "revenue" not in clean:
        return _model("not_applicable", "No financial data was provided.")

    df = clean.copy()
    df["_p"] = pd.PeriodIndex(df["period"], freq="M")
    s = df.dropna(subset=["revenue"]).sort_values("_p")
    n = len(s)
    base = dict(target="revenue", months_with_revenue=n)
    if n < MIN_OBSERVATIONS:
        return _model("skipped_insufficient_data",
                      f"Needs at least {MIN_OBSERVATIONS} months of revenue to forecast and test "
                      f"the forecast (have {n}).", skip_code="too_few_months", **base)
    y = s["revenue"].to_numpy(dtype=float)
    if y.mean() <= 0:
        return _model("skipped_insufficient_data", "Average revenue is not positive.",
                      skip_code="non_positive_revenue", **base)
    x = np.array([p.ordinal for p in s["_p"]], dtype=float)

    x_tr, y_tr, x_te, y_te = x[:-HOLDOUT_MONTHS], y[:-HOLDOUT_MONTHS], x[-HOLDOUT_MONTHS:], y[-HOLDOUT_MONTHS:]
    cands = []
    for name, fn in CANDIDATES.items():
        sc = _scores(y_te, fn(x_tr, y_tr, x_te))
        cands.append({"name": name, **{k: clean_number(v, 2) for k, v in sc.items()}, "_mae": sc["mae"],
                      "_rmse": sc["rmse"], "_mape": sc["mape_pct"]})
    best = min(cands, key=lambda c: (round(c["_mae"], 6), list(CANDIDATES).index(c["name"])))
    naive_mae = next(c["_mae"] for c in cands if c["name"] == "naive")
    public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cands]
    details = dict(base, train_months=len(y_tr), holdout_months=HOLDOUT_MONTHS,
                   model_name=best["name"], candidates=public,
                   mape_pct=clean_number(best["_mape"], 1),
                   beats_naive=bool(best["_mae"] < naive_mae - 1e-9))
    out_scores = dict(mae=clean_number(best["_mae"], 2), rmse=clean_number(best["_rmse"], 2))

    if best["_mape"] is None or best["_mape"] > MAX_MAPE_PCT:
        res = _model("skipped_insufficient_data",
                     f"The best model missed held-out months by too much "
                     f"({'n/a' if best['_mape'] is None else format(best['_mape'], '.0f')}% average error, "
                     f"limit {MAX_MAPE_PCT:.0f}%), so no forecast is shown.",
                     skip_code="poor_accuracy", **details)
        res.update(out_scores)
        return res

    pred = CANDIDATES[best["name"]](x, y, np.arange(x[-1] + 1, x[-1] + 1 + horizon))
    last = s["_p"].iloc[-1]
    rmse = best["_rmse"]
    forecast = [{"period": str(last + i + 1),
                 "value": clean_number(max(v, 0.0), 0),
                 "low": clean_number(max(v - rmse, 0.0), 0),
                 "high": clean_number(max(v + rmse, 0.0), 0)} for i, v in enumerate(pred)]
    caveat = None if details["beats_naive"] else (
        "No candidate predicted the held-out months better than repeating the last month, so this "
        "is effectively a flat expectation rather than a detected trend.")
    res = _model("ok", forecast=forecast, horizon_months=horizon, caveat=caveat,
                 interval_note="low/high = forecast -/+ the holdout RMSE (a typical error, not a "
                               "statistical confidence interval).",
                 **details)
    res.update(out_scores)
    return res
