"""Evidence level: how much the analysis can be trusted, from the data it rests on.

Rules (agreed contract, see README):

* ``high``   -- >= 12 months with revenue, no validation errors in the financial table, AND at
                least one usable, error-free customer or product table.
* ``medium`` -- 6..11 months with revenue, or >= 12 months of financials only (no usable
                customer/product table), or >= 12 months but with validation errors in the
                financial table (rows were excluded, so it cannot be ``high``).
* ``low``    -- fewer than 6 months with revenue (every cold-start business), or no usable
                financial table at all.

The level is a statement about the *data*, not about the business. ``reasons`` explains it in
plain language so the frontend can show why a result is only ``low`` or ``medium``.
"""

from __future__ import annotations

from typing import Any

from .constants import MIN_MONTHS_HIGH, MIN_MONTHS_MEDIUM


def assess_evidence(months_with_revenue: int, financials_report: Any | None,
                    customers_report: Any | None, products_report: Any | None) -> dict[str, Any]:
    """Return ``{"level": "low|medium|high", "reasons": [str, ...]}``.

    The ``*_report`` arguments are ``ValidationReport`` objects (or None when the table was not
    provided). Never raises.
    """
    reasons: list[str] = []
    fin_usable = bool(financials_report is not None and financials_report.is_usable)
    if not fin_usable:
        return {"level": "low",
                "reasons": ["No usable financial table: revenue-based metrics, the health score and "
                            "the forecast are unavailable."]}

    months = int(months_with_revenue or 0)
    fin_clean = financials_report.is_valid
    side_ok = [r for r in (customers_report, products_report)
               if r is not None and r.is_usable and r.is_valid]

    if months < MIN_MONTHS_MEDIUM:
        reasons.append(f"Only {months} month(s) of revenue data; at least {MIN_MONTHS_MEDIUM} are "
                       "needed for medium evidence.")
        level = "low"
    elif months < MIN_MONTHS_HIGH:
        reasons.append(f"{months} months of revenue data; {MIN_MONTHS_HIGH} are needed for high evidence.")
        level = "medium"
    else:
        level = "high"
        if not fin_clean:
            reasons.append("The financial table had validation errors, so some rows were excluded; "
                           "evidence is capped at medium.")
            level = "medium"
        if not side_ok:
            reasons.append("No usable, error-free customer or product data accompanies the financials; "
                           "evidence is capped at medium.")
            level = "medium"

    if level == "high":
        reasons.append(f"{months} months of revenue data with clean financials and supporting "
                       "customer/product data.")
    return {"level": level, "reasons": reasons}
