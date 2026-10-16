"""Validation and cleaning for BizIQ input tables.

Rules (see task 01 of the Person 2 plan):
* Missing values stay missing (NaN) -- they are never silently turned into 0.
* Errors make rows (or the whole dataset) unusable; warnings are noted but data is kept.
* Suspicious records (negative amounts, extreme outliers) are kept but flagged
  in a ``needs_review`` column.
* Results are structured (``ValidationReport``), never just printed.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from .report import ValidationReport

_PERIOD_RE = r"\d{4}-(0[1-9]|1[0-2])"
OUTLIER_FACTOR = 10  # value > 10x median of positive values is flagged
OUTLIER_MIN_OBS = 6  # need this many observations before judging outliers

SPECS: dict[str, dict[str, Any]] = {
    "financials": {
        "required": ["period", "revenue"],
        "optional": ["business_id", "expenses", "expenses_complete"],
        "warn_if_absent": ["expenses", "expenses_complete"],
        "numeric": ["revenue", "expenses"],
        "nonneg": ["revenue", "expenses"],
        "outlier_cols": ["revenue", "expenses"],
        "key": ["period"],
        "ids": [],
        "needs_value": ["revenue"],
    },
    "customers": {
        "required": ["period", "customer_id", "amount_spent"],
        "optional": ["business_id", "transactions"],
        "warn_if_absent": ["transactions"],
        "numeric": ["amount_spent", "transactions"],
        "nonneg": ["amount_spent", "transactions"],
        "outlier_cols": [],
        "key": ["customer_id", "period"],
        "ids": ["customer_id"],
        "needs_value": ["amount_spent"],
    },
    "products": {
        "required": ["period", "product_id", "revenue"],
        "optional": ["business_id", "product_name", "units_sold", "cost"],
        "warn_if_absent": ["units_sold", "cost"],
        "numeric": ["revenue", "units_sold", "cost"],
        "nonneg": ["revenue", "units_sold", "cost"],
        "outlier_cols": [],
        "key": ["product_id", "period"],
        "ids": ["product_id"],
        "needs_value": ["revenue"],
    },
}

_TRUE = {"true", "yes", "y", "1", "t"}
_FALSE = {"false", "no", "n", "0", "f"}


def _rows(work: pd.DataFrame, mask: pd.Series) -> list[int]:
    return [int(r) for r in work.loc[mask, "_row"]]


def _parse_bool(raw: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (parsed object series of True/False/None, mask of unrecognised values)."""
    text = raw.astype("string").str.strip().str.lower()
    present = text.notna() & (text != "")
    parsed = pd.Series([None] * len(raw), index=raw.index, dtype="object")
    parsed[text.isin(_TRUE).fillna(False)] = True
    parsed[text.isin(_FALSE).fillna(False)] = False
    bad = present & parsed.isna()
    return parsed, bad


def validate_table(df: pd.DataFrame | None, dataset: str) -> ValidationReport:
    """Validate and clean one input table. ``dataset`` is financials/customers/products."""
    if dataset not in SPECS:
        raise ValueError(f"Unknown dataset '{dataset}'. Expected one of {list(SPECS)}.")
    spec = SPECS[dataset]
    rep = ValidationReport(dataset=dataset)

    if df is None or not isinstance(df, pd.DataFrame):
        rep.add("error", "no_data", f"No {dataset} data was provided.")
        return rep
    rep.rows_in = len(df)
    if df.empty:
        rep.add("error", "empty_dataset", f"The {dataset} table has no rows.")
        return rep

    work = df.copy().reset_index(drop=True)
    work.columns = [str(c).strip().lower() for c in work.columns]
    work["_row"] = range(len(work))

    missing = [c for c in spec["required"] if c not in work.columns]
    if missing:
        rep.add("error", "missing_required_columns",
                f"Missing required column(s): {', '.join(missing)}.", column=",".join(missing))
        return rep

    for col in spec["optional"]:
        if col not in work.columns:
            work[col] = np.nan if col != "business_id" else None
            if col in spec["warn_if_absent"]:
                rep.add("warning", "missing_optional_column",
                        f"Optional column '{col}' is absent; related metrics will be unavailable.",
                        column=col)

    drop = pd.Series(False, index=work.index)

    # --- periods ---------------------------------------------------------
    period = work["period"].astype("string").str.strip()
    ok_period = period.str.fullmatch(_PERIOD_RE).fillna(False).astype(bool)
    if (~ok_period).any():
        rep.add("error", "invalid_period",
                "Period values must look like YYYY-MM; these rows were excluded.",
                column="period", rows=_rows(work, ~ok_period))
    drop |= ~ok_period
    work["period"] = period

    # --- identifiers -----------------------------------------------------
    for col in spec["ids"]:
        ident = work[col].astype("string").str.strip()
        bad = (ident.isna() | (ident == "")) & ~drop
        if bad.any():
            rep.add("warning", "missing_identifier",
                    f"Rows without a {col} cannot be analysed and were excluded.",
                    column=col, rows=_rows(work, bad))
        drop |= bad
        work[col] = ident

    # --- numeric columns -------------------------------------------------
    review = pd.Series(False, index=work.index)
    for col in spec["numeric"]:
        raw = work[col]
        text = raw.astype("string").str.strip()
        present = (raw.notna() & (text != "")).astype(bool)
        num = pd.to_numeric(raw, errors="coerce").astype("float64")
        inf = pd.Series(np.isinf(num.to_numpy()), index=work.index)
        num[inf] = np.nan
        invalid = ((present & num.isna()) | inf) & ~drop
        if invalid.any():
            rep.add("warning", "invalid_numeric",
                    f"Non-numeric values in '{col}' were treated as missing (not zero).",
                    column=col, rows=_rows(work, invalid))
        absent = ~present & ~drop
        if absent.any() and col in spec["needs_value"] + spec["outlier_cols"]:
            rep.add("warning", "missing_values",
                    f"'{col}' has missing values; they were kept as missing, not zero.",
                    column=col, rows=_rows(work, absent))
        neg = (num < 0) & ~drop
        if neg.any() and col in spec["nonneg"]:
            rep.add("warning", "negative_value",
                    f"Negative values in '{col}' are unusual; rows were kept and flagged for review.",
                    column=col, rows=_rows(work, neg))
            review |= neg
        work[col] = num

    # --- expenses_complete flag (financials) -----------------------------
    if dataset == "financials":
        parsed, bad = _parse_bool(work["expenses_complete"])
        if (bad & ~drop).any():
            rep.add("warning", "invalid_flag",
                    "expenses_complete must be true/false; unrecognised values were treated as unknown.",
                    column="expenses_complete", rows=_rows(work, bad & ~drop))
        work["expenses_complete"] = parsed

    # --- duplicates ------------------------------------------------------
    live = work[~drop]
    cmp_cols = [c for c in work.columns if c != "_row"]
    exact = live.duplicated(subset=cmp_cols, keep="first")
    if exact.any():
        rep.add("warning", "duplicate_rows",
                "Exact duplicate rows were removed (first occurrence kept).",
                rows=_rows(work, work.index.isin(exact[exact].index)))
        drop |= work.index.isin(exact[exact].index)

    live = work[~drop]
    key_dup = live.duplicated(subset=spec["key"], keep=False)
    if key_dup.any():
        conflict_idx = key_dup[key_dup].index
        rep.add("error", "conflicting_duplicates",
                f"Several rows share the same {'+'.join(spec['key'])} with different values; "
                "all of them were excluded because the correct one is unknown.",
                rows=_rows(work, work.index.isin(conflict_idx)))
        drop |= work.index.isin(conflict_idx)

    # --- outliers (flag only) --------------------------------------------
    live = work[~drop]
    for col in spec["outlier_cols"]:
        vals = live[col].dropna()
        pos = vals[vals > 0]
        if len(pos) >= OUTLIER_MIN_OBS:
            thresh = OUTLIER_FACTOR * float(pos.median())
            out = (work[col] > thresh) & ~drop
            if out.any():
                rep.add("warning", "suspicious_outlier",
                        f"'{col}' values above {OUTLIER_FACTOR}x the median were kept and flagged for review.",
                        column=col, rows=_rows(work, out))
                review |= out

    # --- calendar gaps (financials) --------------------------------------
    clean = work[~drop].copy()
    if dataset == "financials" and not clean.empty:
        p = pd.PeriodIndex(clean["period"], freq="M")
        full = pd.period_range(p.min(), p.max(), freq="M")
        gaps = [str(m) for m in full.difference(p)]
        if gaps:
            rep.add("warning", "missing_months",
                    f"No data for {len(gaps)} month(s) between {p.min()} and {p.max()}: "
                    f"{', '.join(gaps[:12])}{'...' if len(gaps) > 12 else ''}. "
                    "Month-on-month comparisons skip these gaps.",
                    column="period")

    # --- usable values ---------------------------------------------------
    if not clean.empty:
        for col in spec["needs_value"]:
            if clean[col].notna().sum() == 0:
                rep.add("error", "no_usable_values",
                        f"No valid numeric '{col}' values remain after cleaning.", column=col)

    clean["needs_review"] = review[~drop].to_numpy()
    clean = clean.drop(columns=["_row"]).sort_values(spec["key"]).reset_index(drop=True)
    rep.clean = clean if not clean.empty else None
    rep.rows_out = len(clean)
    if clean.empty and not rep.errors:
        rep.add("error", "no_usable_rows", f"No usable {dataset} rows remain after cleaning.")
    return rep


def validate_all(data: dict[str, pd.DataFrame | None]) -> dict[str, ValidationReport]:
    """Validate every table in ``data`` (keys: financials, customers, products).

    Tables that are ``None`` or absent are simply skipped -- an absent optional
    table is not an error (e.g. service businesses have no products).
    """
    return {name: validate_table(df, name) for name, df in data.items()
            if name in SPECS and df is not None}
