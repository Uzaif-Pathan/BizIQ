"""Customer segmentation with K-Means (RFM features), evaluated before use.

Method (documented in docs/ENGINE_FORMULAS.md):

* Window: latest 12 calendar months of the validated customers table.
* Features per customer: ``recency_months`` (months since last active month, relative to
  the last month of data), ``frequency_months`` (number of distinct active months) and
  ``log_spend`` = log(1 + total spend). Spend is log-scaled because it is right-skewed.
  Features with zero variance are dropped; all features are standardised (z-scores).
* Eligibility: >= 20 customers, >= 3 months of data, >= 2 informative features.
* k is chosen from 2..5 by the best silhouette score (every candidate must keep every
  cluster at >= 5 % of customers and >= 3 customers). Deterministic: ``random_state=42``.
* Evaluation gate: the segments are only returned if the best silhouette >= 0.25.
  Below that the data has no real group structure and the model reports itself as skipped
  instead of inventing segments. Stability (adjusted Rand index between two different
  random initialisations) is reported.
* Segment names come from simple rules on the cluster averages. They are descriptive
  labels, not model output.

The function never raises: any failure is returned as ``status: "failed"``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from ..common import clean_number
from ..trends import latest_window

MIN_CUSTOMERS = 20
MIN_MONTHS = 3
MIN_FEATURES = 2
K_MIN, K_MAX = 2, 5
MIN_CLUSTER_FRACTION = 0.05
MIN_CLUSTER_SIZE = 3
MIN_SILHOUETTE = 0.25
LAPSED_RECENCY_MONTHS = 3
RANDOM_STATE = 42
FEATURES = ("recency_months", "frequency_months", "log_spend")


def _model(status: str, reason: str | None = None, **details: Any) -> dict[str, Any]:
    d = {k: v for k, v in details.items() if v is not None}
    if reason:
        d["reason"] = reason
    return {"status": status, "mae": None, "rmse": None, "details": d}


def build_rfm(clean: pd.DataFrame) -> tuple[pd.DataFrame, str, int]:
    """Per-customer RFM table for the reporting window. Returns (table, window_label, months)."""
    df = clean.copy()
    df["_p"] = pd.PeriodIndex(df["period"], freq="M")
    win = latest_window(df["_p"].min(), df["_p"].max())
    w = df[df["_p"].isin(win) & df["amount_spent"].notna()]
    last = w["_p"].max() if len(w) else win[-1]
    g = w.groupby("customer_id")
    rfm = pd.DataFrame({
        "recency_months": g["_p"].max().map(lambda p: (last - p).n),
        "frequency_months": g["_p"].nunique(),
        "total_spend": g["amount_spent"].sum(),
    })
    rfm["log_spend"] = np.log1p(rfm["total_spend"].clip(lower=0))
    return rfm, f"{win[0]}/{win[-1]}", int(w["_p"].nunique())


def _label(profile: dict[str, float], med: dict[str, float]) -> str:
    if profile["recency_months"] >= LAPSED_RECENCY_MONTHS:
        return "Lapsed / inactive"
    high_spend = profile["total_spend"] > med["total_spend"]
    frequent = profile["frequency_months"] > med["frequency_months"]
    if high_spend and frequent:
        return "Loyal high-value"
    if high_spend:
        return "High spenders, less frequent"
    if frequent:
        return "Frequent, lower spend"
    return "Occasional, lower spend"


def segment_customers(clean: pd.DataFrame | None) -> dict[str, Any]:
    """K-Means customer segmentation. Returns the contract ``model`` object."""
    try:
        return _segment(clean)
    except Exception as exc:  # noqa: BLE001 - the engine must never raise on a model failure
        return _model("failed", f"Segmentation failed: {type(exc).__name__}: {exc}")


def _segment(clean: pd.DataFrame | None) -> dict[str, Any]:
    if clean is None or len(clean) == 0:
        return _model("not_applicable", "No customer-level data was provided.")

    rfm, window, n_months = build_rfm(clean)
    n = len(rfm)
    base = dict(window=window, n_customers=n, months_of_data=n_months)
    if n_months < MIN_MONTHS:
        return _model("skipped_insufficient_data",
                      f"Needs at least {MIN_MONTHS} months of customer data (have {n_months}).",
                      skip_code="too_few_months", **base)
    if n < MIN_CUSTOMERS:
        return _model("skipped_insufficient_data",
                      f"Needs at least {MIN_CUSTOMERS} customers (have {n}).",
                      skip_code="too_few_customers", **base)

    used = [f for f in FEATURES if rfm[f].nunique() > 1]
    dropped = [f for f in FEATURES if f not in used]
    if len(used) < MIN_FEATURES:
        return _model("skipped_insufficient_data",
                      "Customers are almost identical on recency, frequency and spend, "
                      "so there is nothing to separate into segments.",
                      skip_code="no_variation", features_dropped=dropped or None, **base)

    X = StandardScaler().fit_transform(rfm[used].to_numpy(dtype=float))
    if len(np.unique(X, axis=0)) < K_MIN + 1:
        return _model("skipped_insufficient_data", "Too few distinct customer profiles to cluster.",
                      skip_code="no_variation", **base)

    k_scores: dict[int, float] = {}
    fits: dict[int, np.ndarray] = {}
    for k in range(K_MIN, min(K_MAX, n // MIN_CLUSTER_SIZE) + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit_predict(X)
        sizes = np.bincount(labels, minlength=k)
        if sizes.min() < max(MIN_CLUSTER_SIZE, int(np.ceil(MIN_CLUSTER_FRACTION * n))):
            continue
        k_scores[k] = float(silhouette_score(X, labels))
        fits[k] = labels
    if not k_scores:
        return _model("skipped_insufficient_data",
                      "No cluster count produced segments of a sensible size.",
                      skip_code="no_valid_k", **base)

    best_k = max(k_scores, key=k_scores.get)
    sil = k_scores[best_k]
    details = dict(base, features=used, features_dropped=dropped or None,
                   scaling="StandardScaler (z-score); spend log-transformed",
                   k_scores={str(k): clean_number(v, 3) for k, v in k_scores.items()},
                   silhouette=clean_number(sil, 3))
    if sil < MIN_SILHOUETTE:
        return _model("skipped_insufficient_data",
                      f"No clear segment structure in the data (best silhouette {sil:.2f} < "
                      f"{MIN_SILHOUETTE}), so no segments are shown.",
                      skip_code="weak_structure", **details)

    alt = KMeans(n_clusters=best_k, n_init=10, random_state=RANDOM_STATE + 1).fit_predict(X)
    labels = fits[best_k]
    rfm = rfm.assign(cluster=labels)
    med = rfm[["total_spend", "frequency_months"]].median().to_dict()
    total = float(rfm["total_spend"].sum())
    segments = []
    for c, grp in rfm.groupby("cluster"):
        prof = {"recency_months": float(grp["recency_months"].mean()),
                "frequency_months": float(grp["frequency_months"].mean()),
                "total_spend": float(grp["total_spend"].mean())}
        segments.append({
            "name": _label(prof, med),
            "customers": int(len(grp)),
            "customers_share_pct": clean_number(len(grp) / n * 100, 1),
            "spend_share_pct": clean_number(grp["total_spend"].sum() / total * 100, 1) if total > 0 else None,
            "avg_recency_months": clean_number(prof["recency_months"], 1),
            "avg_active_months": clean_number(prof["frequency_months"], 1),
            "avg_spend": clean_number(prof["total_spend"], 2),
        })
    segments.sort(key=lambda s: -(s["spend_share_pct"] or 0))
    return _model("ok", k=best_k, segments=segments,
                  stability_ari=clean_number(adjusted_rand_score(labels, alt), 3),
                  **{kk: vv for kk, vv in details.items()})
