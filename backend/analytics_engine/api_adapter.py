"""Convert the engine's native result into the API contract used by the backend and frontend.

Why this exists: ``run_analysis`` returns a rich native format (contracts/engine-result.schema.json).
The backend's Pydantic models (backend/app/schemas/analysis.py) and
contracts/analysis-result.schema.json use a flatter shape with different field names. This module
is the one place that translates between them, so neither side has to change its own core files.

Mapping (documented in docs/PERSON3_INTEGRATION.md):

* metrics: each ``{"value", ...}`` object -> a flat number or null; ``profit_margin_pct`` is exposed as
  ``profit_margin`` (the contract's headline name). Units, periods, formulas, reasons and notes for
  every metric are kept in the optional ``metric_details``.
* findings: ``id`` -> ``finding_id``; ``type`` -> a readable ``title`` and a ``category``;
  ``metric``/``value`` -> ``metric_name``/``metric_value``; severity info/low -> info,
  medium -> warning, high -> critical; the text goes to ``description`` and ``evidence`` (list).
* recommendations: ``id`` -> ``recommendation_id``; ``finding_ids`` -> ``supporting_finding_ids``;
  ``rationale`` -> ``reason``; ``expected_direction`` object -> its direction string or null.
* status: completed and partial -> ``completed`` (the raw value stays in ``engine_status``, and a
  limitation explains partial runs); failed -> ``failed`` with ``error_message``;
  failed runs get ``evidence_level: "insufficient"``.
* ``limitations`` collects every reason a reader needs: why headline metrics are null, evidence notes,
  skipped models, missing benchmarks, an unavailable health score.
* Extras passed through unchanged: ``health_score``, ``models``, ``validation``, ``data_coverage``,
  ``series`` (chart-ready monthly financial / customer rows and the product table).

``to_api_result`` never raises. ``to_service_output`` is for the backend's ``analysis_service`` (which
supplies the ids, status and timestamps itself) and raises ``EngineRunFailed`` when the engine
could not analyse the data, so the service records a failed run instead of a false "completed".
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import __version__
from .pipeline import run_analysis

HEADLINE = ("revenue", "expenses", "profit", "profit_margin")
METRIC_ALIASES = {"profit_margin_pct": "profit_margin"}
SEVERITY_MAP = {"info": "info", "low": "info", "medium": "warning", "high": "critical"}
SERVICE_RESERVED = ("analysis_id", "business_id", "status", "created_at", "completed_at")
ENGINE_BUSINESS_TYPES = {"retail": "retail", "service": "service"}  # anything else -> "other"
DATA_QUALITY_TYPES = {"data_needs_review", "expense_definition_incomplete",
                      "customer_data_coverage_low", "product_data_coverage_low"}
MODEL_LABELS = {"segmentation": "Customer segmentation", "forecast": "Revenue forecast"}

TITLES = {
    "profit_margin_level": "Profit margin", "expense_definition_incomplete": "Profit cannot be calculated yet",
    "loss_months": "Months where costs exceeded revenue", "revenue_decline_yoy": "Revenue is down year on year",
    "revenue_decline_mom": "Revenue fell compared with last month", "revenue_growth_12m": "12-month revenue growth",
    "expenses_outpacing_revenue": "Costs are growing faster than sales",
    "revenue_volatility": "Revenue varies a lot from month to month", "data_needs_review": "Some records need review",
    "revenue_trend_increasing": "Revenue trend: increasing", "revenue_trend_decreasing": "Revenue trend: decreasing",
    "revenue_trend_flat": "Revenue trend: flat", "revenue_trend_unclear": "Revenue trend: no clear direction",
    "repeat_customers": "Repeat customers", "repeat_customers_low": "Few customers come back",
    "customer_retention": "Customer retention", "customer_retention_low": "Low customer retention",
    "customer_concentration": "Customer concentration",
    "active_customers_increasing": "Active customers are increasing",
    "active_customers_decreasing": "Active customers are decreasing",
    "customer_data_coverage_low": "Customer records cover only part of revenue",
    "product_concentration": "Product concentration", "negative_margin_product": "Product sold below cost",
    "low_margin_main_product": "Main product has a thin margin",
    "product_revenue_declining": "Product revenue is declining", "product_losing_share": "Product is losing share",
    "product_gaining_share": "Product is gaining share",
    "low_contribution_products": "Several products contribute very little",
    "product_data_coverage_low": "Product records cover only part of revenue",
}


class EngineRunFailed(Exception):
    """The engine could not analyse the data (e.g. no usable financials)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ---------------------------------------------------------------------------------------------
def business_to_engine_input(business: Any) -> dict[str, Any]:
    """Backend business (Pydantic object or dict) -> the dict ``run_analysis`` expects.

    ``manufacturing`` and ``hybrid`` have no dedicated rules yet and map to ``other``.
    """
    def get(name: str):
        v = business.get(name) if isinstance(business, Mapping) else getattr(business, name, None)
        return getattr(v, "value", v)  # Enum -> its value

    btype = str(get("business_type") or "").strip().lower()
    place = ", ".join(str(p) for p in (get("city"), get("district"), get("state")) if p)
    return {"business_id": str(get("id") or get("business_id") or ""),
            "business_type": ENGINE_BUSINESS_TYPES.get(btype, "other"),
            "industry": get("industry"), "location": place or None}


def _category(f: dict[str, Any]) -> str:
    t, fid = f.get("type", ""), str(f.get("id", ""))
    if t in DATA_QUALITY_TYPES:
        return "data_quality"
    if t.startswith("revenue_trend"):
        return "trend"
    return "customer" if fid.startswith("CUS-") else "product" if fid.startswith("PRD-") else "financial"


def _title(f: dict[str, Any]) -> str:
    base = TITLES.get(f.get("type", ""), str(f.get("type", "Finding")).replace("_", " ").capitalize())
    if re.fullmatch(r"PRD-[A-Z]+-.+", str(f.get("id", ""))):  # per-product finding: name the product
        m = re.search(r"'([^']+)'", str(f.get("evidence", "")))
        if m:
            return f"{base}: {m.group(1)}"
    return base


def _finding(f: dict[str, Any]) -> dict[str, Any]:
    value = f.get("value")
    ev = ([f"{f['metric']} = {value}"] if f.get("metric") and value is not None else [])
    if f.get("comparison"):
        ev.append(f"Reference: {f['comparison']}")
    return {"finding_id": str(f["id"]), "category": _category(f), "title": _title(f),
            "description": str(f.get("evidence", "")), "metric_name": f.get("metric"),
            "metric_value": value if isinstance(value, (int, float)) else None,
            "severity": SEVERITY_MAP.get(f.get("severity"), "info"), "evidence": ev}


def _recommendation(r: dict[str, Any]) -> dict[str, Any]:
    out = {"recommendation_id": str(r["id"]), "title": str(r["issue"]).rstrip("."), "issue": r["issue"],
           "reason": r.get("rationale", ""), "action": r["action"], "priority": r["priority"],
           "supporting_finding_ids": list(r["finding_ids"]),
           "evidence": [r["evidence"]] if r.get("evidence") else [],
           "kpi": r.get("kpi"),
           "expected_direction": (r.get("expected_direction") or {}).get("direction"),
           "supporting_metric": r.get("supporting_metric"), "rule_id": r.get("rule_id")}
    if r.get("caveat"):
        out["caveat"] = r["caveat"]
    return out


def _flat_metrics(metrics: Mapping[str, Any]) -> tuple[dict[str, float | None], dict[str, Any]]:
    flat: dict[str, float | None] = {k: None for k in HEADLINE}
    details: dict[str, Any] = {}
    for key, m in metrics.items():
        name = METRIC_ALIASES.get(key, key)
        v = m.get("value") if isinstance(m, Mapping) else None
        flat[name] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        if isinstance(m, Mapping):
            details[name] = {k: m[k] for k in ("unit", "period", "formula", "reason", "note") if m.get(k) is not None}
    return flat, details


def _limitations(res: Mapping[str, Any], details: Mapping[str, Any], flat: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    if res.get("evidence_level") != "high":
        out += [str(n) for n in res.get("evidence_notes") or []]
    if res.get("status") == "partial":
        out.append("Some input rows or tables had validation errors and were excluded; see validation for details.")
    for k in HEADLINE:
        if flat.get(k) is None and details.get(k, {}).get("reason"):
            out.append(f"{k.replace('_', ' ').capitalize()} is not available: {details[k]['reason']}.")
    for name, model in (res.get("models") or {}).items():
        if model.get("status") in ("skipped_insufficient_data", "failed"):
            reason = (model.get("details") or {}).get("reason")
            if reason:
                out.append(f"{MODEL_LABELS.get(name, name)}: {reason}")
    hs = res.get("health_score") or {}
    if hs and hs.get("score") is None and hs.get("limitations"):
        out.append(f"Health score: {hs['limitations'][0]}")
    if res.get("benchmark_status") == "unavailable":
        out.append("Benchmark comparison is unavailable; no industry benchmark was used.")
    return list(dict.fromkeys(out))  # de-duplicate, keep order


def _failed(analysis_id: str, business_id: str, message: str, code: str | None = None) -> dict[str, Any]:
    return {"analysis_id": analysis_id, "business_id": business_id, "status": "failed",
            "metrics": {k: None for k in HEADLINE}, "findings": [], "recommendations": [],
            "evidence_level": "insufficient", "benchmark_status": "unavailable",
            "method_version": f"analytics_engine-{__version__}", "limitations": [], "error_message": message,
            "engine_status": "failed", **({"error_code": code} if code else {})}


def to_api_result(res: Mapping[str, Any]) -> dict[str, Any]:
    """Native engine result -> API contract dict. Never raises."""
    aid, bid = str((res or {}).get("analysis_id", "")) if isinstance(res, Mapping) else "", \
        str((res or {}).get("business_id", "")) if isinstance(res, Mapping) else ""
    try:
        if res.get("status") == "failed":
            err = res.get("error") or {}
            out = _failed(aid, bid, err.get("message") or "The analysis could not be completed.", err.get("code"))
            out["limitations"] = [n for n in res.get("evidence_notes") or []]
            if res.get("validation"):
                out["validation"] = res["validation"]
            return out
        flat, details = _flat_metrics(res.get("metrics") or {})
        out = {"analysis_id": aid, "business_id": bid, "status": "completed", "metrics": flat,
               "findings": [_finding(f) for f in res.get("findings") or []],
               "recommendations": [_recommendation(r) for r in res.get("recommendations") or []],
               "evidence_level": res["evidence_level"], "benchmark_status": res["benchmark_status"],
               "method_version": f"analytics_engine-{res.get('engine_version', __version__)}",
               "limitations": _limitations(res, details, flat), "engine_status": res["status"],
               "metric_details": details}
        for extra in ("health_score", "models", "validation", "data_coverage", "series"):
            if res.get(extra) is not None:
                out[extra] = res[extra]
        return out
    except Exception as exc:  # noqa: BLE001 - conversion must never break the API
        return _failed(aid, bid, "The analysis result could not be converted to the API format.",
                       f"adapter_error:{type(exc).__name__}")


def to_service_output(res: Mapping[str, Any]) -> dict[str, Any]:
    """Output for ``AnalyticsEngine`` in backend/app/services/analytics_service.py.

    The service passes ``**output`` to ``AnalysisResult`` next to ``analysis_id``, ``business_id``,
    ``status`` and the timestamps, so those keys are removed here. Raises ``EngineRunFailed`` when the
    engine failed (the service then records a failed run).
    """
    api = to_api_result(res)
    if api["status"] == "failed":
        raise EngineRunFailed(api.get("error_code") or "analysis_failed", api["error_message"])
    return {k: v for k, v in api.items() if k not in SERVICE_RESERVED}


def run_for_service(business: Any, data: dict[str, Any], benchmarks: list[dict] | None = None) -> dict[str, Any]:
    """One call for the backend: map the business, run the engine, return service-ready output."""
    return to_service_output(run_analysis(business_to_engine_input(business), data, benchmarks))
