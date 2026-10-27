"""``run_analysis``: the single entry point Person 3's adapter calls.

    run_analysis(business, data, benchmarks=None) -> dict   (see contracts/analysis-result.schema.json)

* ``business``   dict: business_id, business_type (retail|service|other), industry, location
* ``data``       dict with optional DataFrames under ``financials``, ``customers``, ``products``
* ``benchmarks`` optional list of ``{metric, value, source, year, geography, geography_level,
                 definition}`` already filtered by the caller; matched by exact ``metric`` name

The function never raises for bad data, a missing table or a failed model: it returns a result
with ``status`` ``partial`` or ``failed`` and explains why in ``validation`` / ``error``.
"""

from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .constants import BUSINESS_TYPES
from .customers import analyze_customers, build_customer_findings
from .evidence import assess_evidence
from .financial import analyze_financials, build_financial_findings
from .ml import forecast_revenue, segment_customers
from .products import analyze_products, build_product_findings
from .recommendations import build_recommendations
from .scoring import compute_health_score
from .validation import Issue, validate_all


PRODUCT_SERIES_KEYS = ("product_id", "product_name", "months_active", "revenue", "units_sold", "cost",
                       "gross_profit", "gross_margin_pct", "revenue_share_pct", "rank_by_revenue")


def _jsonable(x: Any) -> Any:
    """Recursively convert numpy / pandas scalars and NaN/inf so the result is JSON-safe."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(x, (pd.Period, pd.Timestamp)):
        return str(x)
    if x is pd.NA or x is pd.NaT:
        return None
    return x


def _issue(severity: str, code: str, message: str, dataset: str | None = None) -> dict[str, Any]:
    return Issue(severity, code, message, dataset=dataset).to_dict()


def _safe(label: str, fn, *args, default=None, notes: list | None = None, **kwargs):
    """Run one analysis step; on an unexpected exception record a warning and return default."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the engine must never raise
        if notes is not None:
            notes.append(_issue("warning", "module_failed",
                                f"The {label} step failed ({type(exc).__name__}) and was skipped.", label))
        return default


def _empty_fin() -> dict[str, Any]:
    return analyze_financials(None)


def _failed(analysis_id: str, business_id: str, code: str, message: str,
            validation: dict | None = None) -> dict[str, Any]:
    return _jsonable({
        "analysis_id": analysis_id, "business_id": business_id, "status": "failed",
        "evidence_level": "low", "evidence_notes": [message], "benchmark_status": "unavailable",
        "error": {"code": code, "message": message},
        "validation": validation or {"errors": [], "warnings": [], "datasets": {}},
        "metrics": {}, "findings": [], "recommendations": [], "health_score": None,
        "models": {"segmentation": {"status": "not_applicable"}, "forecast": {"status": "not_applicable"}},
        "data_coverage": {}, "engine_version": __version__,
    })


def _benchmark_status(fin_metrics: dict, pro_metrics: dict, health: dict | None) -> str:
    """available = every benchmarkable metric we computed was compared; partial = some; else unavailable."""
    benchmarkable = set()
    if (fin_metrics.get("profit_margin_pct") or {}).get("value") is not None:
        benchmarkable.add("profit_margin_pct")
    if (pro_metrics.get("gross_margin_pct") or {}).get("value") is not None:
        benchmarkable.add("gross_margin_pct")
    used = {c.get("metric") for c in (health or {}).get("components", []) if c.get("basis") == "benchmark"}
    used &= benchmarkable
    if not benchmarkable or not used:
        return "unavailable"
    return "available" if used == benchmarkable else "partial"


def run_analysis(business: dict | None, data: dict | None,
                 benchmarks: list[dict] | None = None) -> dict[str, Any]:
    analysis_id = str(uuid.uuid4())
    business_id = "unknown"
    try:
        business = business if isinstance(business, dict) else {}
        business_id = str(business.get("business_id") or "unknown")
        if not isinstance(data, dict):
            return _failed(analysis_id, business_id, "invalid_input",
                           "`data` must be a dict with optional DataFrames: financials, customers, products.")
        return _jsonable(_run(analysis_id, business_id, business, data, benchmarks))
    except Exception as exc:  # noqa: BLE001 - last-resort guard
        return _failed(analysis_id, business_id, "internal_error",
                       f"Unexpected error ({type(exc).__name__}); the analysis could not be completed.")


def _run(analysis_id, business_id, business, data, benchmarks) -> dict[str, Any]:
    notes: list[dict[str, Any]] = []

    # --- business type ---------------------------------------------------
    btype = str(business.get("business_type") or "").strip().lower()
    if btype not in BUSINESS_TYPES:
        notes.append(_issue("warning", "unknown_business_type",
                            f"business_type '{business.get('business_type')}' is not one of "
                            f"{list(BUSINESS_TYPES)}; generic ('other') wording is used.", "business"))
        btype = "other"

    # --- validation ------------------------------------------------------
    reports = validate_all({k: v for k, v in data.items()})
    errors = [i.to_dict() for r in reports.values() for i in r.errors]
    warnings = [i.to_dict() for r in reports.values() for i in r.warnings]
    datasets = {n: {"is_valid": r.is_valid, "is_usable": r.is_usable,
                    "rows_in": r.rows_in, "rows_out": r.rows_out} for n, r in reports.items()}

    def clean(name):
        r = reports.get(name)
        return r.clean if r is not None and r.is_usable else None

    fin_clean, cus_clean, pro_clean = clean("financials"), clean("customers"), clean("products")
    if fin_clean is None and cus_clean is None and pro_clean is None:
        return _failed(analysis_id, business_id, "no_usable_data",
                       "None of the provided tables could be used; see validation for the reasons.",
                       {"errors": errors, "warnings": warnings + notes, "datasets": datasets})

    # --- analytics -------------------------------------------------------
    fin = _safe("financials", analyze_financials, fin_clean, default=_empty_fin(), notes=notes)
    fin_metrics = fin.get("metrics", {})
    rev_win = (fin_metrics.get("revenue") or {}).get("value")
    cov = fin.get("coverage", {})
    window = (cov["window_first"], cov["window_last"]) if cov.get("window_first") else None
    cus = _safe("customers", analyze_customers, cus_clean, rev_win, window, notes=notes)
    pro = _safe("products", analyze_products, pro_clean, rev_win, window, notes=notes)

    # --- evidence --------------------------------------------------------
    ev = assess_evidence(cov.get("months_with_revenue", 0), reports.get("financials"),
                         reports.get("customers"), reports.get("products"))

    # --- findings, recommendations, score, models ------------------------
    findings: list[dict[str, Any]] = []
    findings += _safe("financial findings", build_financial_findings, fin, default=[], notes=notes)
    if cus:
        findings += _safe("customer findings", build_customer_findings, cus, default=[], notes=notes)
    if pro:
        findings += _safe("product findings", build_product_findings, pro, default=[], notes=notes)
    recs = _safe("recommendations", build_recommendations, findings, btype, ev["level"],
                 default=[], notes=notes)
    health = _safe("health score", compute_health_score, fin if fin_clean is not None else None,
                   cus, pro, benchmarks, default=None, notes=notes)
    models = {
        "segmentation": _safe("segmentation", segment_customers, cus_clean,
                              default={"status": "failed"}, notes=notes),
        "forecast": _safe("forecast", forecast_revenue, fin_clean,
                          default={"status": "failed"}, notes=notes),
    }

    metrics: dict[str, Any] = {}
    for part in (fin, cus, pro):
        if part:
            metrics.update(part.get("metrics", {}))

    # --- chart-ready series (no per-customer rows: customer ids are not needed for charts) ----
    series = {
        "financial_monthly": fin.get("monthly", []) if fin_clean is not None else [],
        "customer_monthly": (cus or {}).get("monthly", []) if cus_clean is not None else [],
        "products": ([{k: row.get(k) for k in PRODUCT_SERIES_KEYS} for row in (pro or {}).get("products", [])]
                     if pro_clean is not None else []),
    }

    # --- status ----------------------------------------------------------
    expected_unusable = [n for n, r in reports.items() if not r.is_usable]
    partial = bool(errors) or bool(expected_unusable) or fin_clean is None or \
        any(i["code"] == "module_failed" for i in notes)
    all_notes = warnings + notes
    if fin_clean is None:
        all_notes.append(_issue("warning", "no_financial_data",
                                "No usable financial table: only customer/product analytics are shown.",
                                "financials"))

    return {
        "analysis_id": analysis_id, "business_id": business_id,
        "status": "partial" if partial else "completed",
        "evidence_level": ev["level"], "evidence_notes": ev["reasons"],
        "benchmark_status": _benchmark_status(fin_metrics, (pro or {}).get("metrics", {}), health),
        "error": None,
        "validation": {"errors": errors, "warnings": all_notes, "datasets": datasets},
        "metrics": metrics, "findings": findings, "recommendations": recs,
        "health_score": health, "models": models,
        "data_coverage": {"financials": cov if fin_clean is not None else None,
                          "customers": (cus or {}).get("coverage") if cus_clean is not None else None,
                          "products": (pro or {}).get("coverage") if pro_clean is not None else None},
        "series": series, "business_type": btype, "engine_version": __version__,
    }
