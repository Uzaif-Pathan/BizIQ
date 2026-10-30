"""Benchmark lookup: context numbers from the ASUSE survey, shown next to a business, never mixed into
the engine's calculations.

What the numbers are: government survey averages for unincorporated non-agricultural establishments
(value added and pay), not profit margins. Do NOT compare them with the business's profit margin.

Geography: the lookup tries district, then state, then region, then national, and reports which level was
used. This file only has state and national rows, so district and region find nothing. Detailed industries
(for example "Other Retail Trade") exist only at national level; at state level only broad sectors
(All, Manufacturing, Trade, Other Services) exist, so a state result can be broader than a national one.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# metric -> (label, plain-language definition)
METRICS = {
    "gva_per_establishment": ("Value added per establishment",
                              "Average gross value added per establishment per year (Rs). Value added is sales minus "
                              "inputs; it is not profit."),
    "gva_per_worker": ("Value added per worker",
                       "Average gross value added per worker per year (Rs). It is not profit."),
    "emolument_per_hired_worker": ("Pay per hired worker",
                                   "Average yearly emoluments (pay and benefits) per hired worker (Rs)."),
}
CONTEXT_NOTE = ("Survey averages for unincorporated non-agricultural establishments (market establishments). "
                "They describe value added and pay, not profit, so do not compare them with profit margin.")

# (keywords in the business's industry text) -> (broad sector at state level, detailed activity at national level)
INDUSTRY_RULES = [
    (("wholesale",), ("Trade", "Other Wholesale Trade")),
    (("retail", "grocery", "kirana", "provision", "general store", "supermarket", "shop", "store", "stationery",
      "pharmacy", "chemist", "bakery"), ("Trade", "Other Retail Trade")),
    (("restaurant", "cafe", "hotel", "food service", "catering", "dhaba", "accommodation"),
     ("Other Services", "Food and Accommodation Service Activities")),
    (("repair", "garage", "workshop"), ("Other Services", "Maintenance and Repair of Motor Vehicles and Motor Cycles")),
    (("education", "coaching", "tuition", "school"), ("Other Services", "Education")),
    (("transport", "logistics", "taxi", "cab"), ("Other Services", "Land Transport")),
    (("health", "clinic", "diagnostic"), ("Other Services", "Human Health and Social Work Activities")),
    (("manufactur", "factory", "production"), ("Manufacturing", "Manufacturing Activities")),
]
TYPE_FALLBACK = {"retail": ("Trade", "Other Retail Trade"), "service": ("Other Services", "Other Services")}
STATE_ALIASES = {"puducherry": "Puduchery", "pondicherry": "Puduchery", "orissa": "Odisha",
                 "jammu and kashmir": "Jammu & Kashmir", "dadra and nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
                 "daman and diu": "Dadra & Nagar Haveli and Daman & Diu"}


def _norm(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("&", " and ")).strip()


def match_industry(industry: Optional[str], business_type: Optional[str]) -> Dict[str, Any]:
    """Map free text to survey categories. ``match`` says how sure we are: keyword, business_type or none."""
    text = _norm(industry)
    for words, (broad, detailed) in INDUSTRY_RULES:
        if any(w in text for w in words):
            return {"broad_sector": broad, "activity": detailed, "match": "keyword"}
    fallback = TYPE_FALLBACK.get(_norm(business_type))
    if fallback:
        return {"broad_sector": fallback[0], "activity": fallback[1], "match": "business_type"}
    return {"broad_sector": "All", "activity": "All", "match": "none"}


def match_state(state: Optional[str], known_states: Iterable[str]) -> Optional[str]:
    key = _norm(state)
    if not key:
        return None
    key = _norm(STATE_ALIASES.get(key, key))
    for s in known_states:
        if _norm(s) == key:
            return s
    return None


def _specificity(row: Dict[str, Any]) -> str:
    """How narrow the row's industry is: all_industries, broad_sector (state level) or detailed_activity."""
    if row["industry_name"] == "All":
        return "all_industries"
    if row["geography_level"] == "STATE":
        return "broad_sector"
    return "detailed_activity"


SPECIFICITY_NOTES = {
    "all_industries": "Covers all industries together, so it is not specific to this business's category.",
    "broad_sector": "Broad sector only (state data is not split into detailed activities), so it is less specific "
                    "than the national activity comparison.",
    "detailed_activity": "Specific activity category, national level only.",
}


def _worker_group(metric: str) -> str:
    return "All" if metric == "emolument_per_hired_worker" else "not_applicable"


def select_benchmarks(rows: List[Dict[str, Any]], business: Dict[str, Any]) -> Dict[str, Any]:
    """Pick benchmark rows for one business from candidate rows (dicts with the industry_benchmarks columns).

    ``business`` has industry, business_type, state, district (all optional). Returns the API payload.
    """
    profile = match_industry(business.get("industry"), business.get("business_type"))
    states = {r["state"] for r in rows if r.get("state")}
    state = match_state(business.get("state"), states)
    items: List[Dict[str, Any]] = []
    tried = ["district", "state", "region", "national"]
    for metric, (label, definition) in METRICS.items():
        wanted = {"sector": "Combined", "establishment_type": "All", "worker_group": _worker_group(metric)}
        pool = [r for r in rows if r["metric_name"] == metric
                and all(r.get(k) == v for k, v in wanted.items())]
        candidates = []
        if state:  # state rows only exist for broad sectors
            candidates += [r for r in pool if r["geography_level"] == "STATE" and r.get("state") == state
                           and r["industry_name"] == profile["broad_sector"]]
        candidates += [r for r in pool if r["geography_level"] == "NATIONAL"
                       and r["industry_name"] == profile["activity"]]
        for r in candidates:
            specificity = _specificity(r)
            items.append({
                "metric": metric, "label": label, "definition": definition,
                "value": float(r["metric_value"]), "unit": r.get("metric_unit"),
                "geography_level_used": r["geography_level"].lower(),
                "geography": r.get("state") or "India",
                "industry_used": r["industry_name"], "sector": r["sector"],
                "establishment_type": r["establishment_type"], "worker_group": r["worker_group"],
                "year": r["reference_year"], "source": r.get("source_name") or "ASUSE 2025",
                "note": r.get("confidence_note"),
                "specificity": specificity, "specificity_note": SPECIFICITY_NOTES[specificity],
            })
    notes = [CONTEXT_NOTE]
    if profile["match"] == "business_type":
        notes.append("The industry text could not be matched to a survey category; the business type was used instead.")
    if profile["match"] == "none":
        notes.append("No survey category matched this business, so all-industry figures were used.")
    if business.get("state") and not state:
        notes.append(f"No survey data was found for the state '{business['state']}'; only national figures are shown.")
    if not business.get("state"):
        notes.append("The business has no state recorded; only national figures are shown.")
    if len({i["specificity"] for i in items}) > 1:
        notes.append("State figures cover a broad sector, while national figures cover a specific activity. "
                     "They are not equally specific, so do not read the two as the same comparison.")
    notes.append("District and region level figures are not available in this data.")
    status = "unavailable" if not items else ("available" if profile["match"] == "keyword" else "partial")
    return {"status": status, "items": items, "matched_industry": profile, "matched_state": state,
            "levels_tried": tried, "notes": notes}


def load_candidate_rows(db) -> List[Dict[str, Any]]:
    """All non-count benchmark rows (Combined sector) from the database, with the source name."""
    from sqlalchemy import select

    from app.models import BenchmarkSource, IndustryBenchmark

    stmt = (select(IndustryBenchmark, BenchmarkSource.source_name)
            .join(BenchmarkSource, BenchmarkSource.source_id == IndustryBenchmark.source_id)
            .where(IndustryBenchmark.metric_name.in_(list(METRICS)), IndustryBenchmark.sector == "Combined"))
    out = []
    for b, source_name in db.execute(stmt):
        out.append({c.name: getattr(b, c.name) for c in IndustryBenchmark.__table__.columns} | {"source_name": source_name})
    return out
