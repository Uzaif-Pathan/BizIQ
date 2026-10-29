"""Reads an uploaded CSV, validates it with the analytics engine's validator and prepares rows to store.

This module has no web or database code, so it can be tested on its own.

Rules (the same ones the engine follows):
* a missing value stays missing (None), never 0;
* rows the validator rejects are not stored; every rejection is reported as an issue;
* a file with no usable row fails the import and stores nothing.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from analytics_engine.validation.validator import validate_table
from app.schemas.data_import import ImportDataType, ImportStatus, IssueSeverity, ValidationIssueCreate

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
MAX_ISSUE_ROWS = 50  # one stored issue per affected row, but at most this many per problem


class ImportFileError(Exception):
    """The file cannot be read at all (not a CSV, too big, empty). Message is safe to show."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ProcessedImport:
    status: ImportStatus  # COMPLETED, COMPLETED_WITH_WARNINGS or FAILED
    rows_received: int
    rows_accepted: int
    issues: List[ValidationIssueCreate] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)  # clean rows ready to store

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)


def read_csv(content: bytes) -> pd.DataFrame:
    if not content or not content.strip():
        raise ImportFileError("The file is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise ImportFileError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.", 413)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportFileError("The file is not UTF-8 text. Please save it as a CSV (UTF-8).")
    try:
        # dtype=str: the validator decides what is a number; nothing is guessed (or zero-filled) here.
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, na_values=[""])
    except Exception:
        raise ImportFileError("The file could not be read as a CSV.")
    if len(df) > MAX_ROWS:
        raise ImportFileError(f"The file has more than {MAX_ROWS} rows.", 413)
    return df


def _issues(report) -> List[ValidationIssueCreate]:
    out: List[ValidationIssueCreate] = []
    for issue in [*report.errors, *report.warnings]:
        severity = IssueSeverity.ERROR if issue.severity == "error" else IssueSeverity.WARNING
        base = dict(severity=severity, code=issue.code[:100], message=issue.message[:500], column=issue.column)
        if issue.rows:
            for pos in issue.rows[:MAX_ISSUE_ROWS]:
                # 1-based position among the data rows (the header line is not counted)
                out.append(ValidationIssueCreate(**base, row_number=int(pos) + 1))
        else:
            out.append(ValidationIssueCreate(**base))
    return out


def _clean(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if v is pd.NA or v is pd.NaT:
        return None
    return v


def _period(p: str) -> date:
    y, m = str(p).split("-")
    return date(int(y), int(m), 1)


def _num(v: Any) -> Optional[float]:
    v = _clean(v)
    return None if v is None else float(v)


def _int(v: Any) -> Optional[int]:
    v = _num(v)
    return None if v is None else int(round(v))


def _storage_rows(data_type: ImportDataType, clean: pd.DataFrame) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in clean.to_dict("records"):
        period = _period(r["period"])
        if data_type == ImportDataType.FINANCIALS:
            flag = _clean(r.get("expenses_complete"))
            rows.append({
                "period_start": period,
                "revenue": _num(r.get("revenue")),
                "expenses": _num(r.get("expenses")),  # stored as other_expenses (a single total)
                "expenses_complete": None if flag is None else bool(flag),
            })
        elif data_type == ImportDataType.CUSTOMERS:
            rows.append({
                "period_start": period,
                "customer_ref": str(r["customer_id"]),
                "transactions": _int(r.get("transactions")),
                "amount_spent": _num(r.get("amount_spent")),
            })
        else:
            name = _clean(r.get("product_name"))
            rows.append({
                "period_start": period,
                "product_ref": str(r["product_id"]),
                "product_name": None if name is None else str(name),
                "units_sold": _int(r.get("units_sold")),
                "revenue": _num(r.get("revenue")),
                "cost": _num(r.get("cost")),  # total cost of what was sold that month
            })
    return rows


_NUMERIC_COLUMNS = {
    ImportDataType.FINANCIALS: ["revenue", "expenses"],
    ImportDataType.CUSTOMERS: ["amount_spent", "transactions"],
    ImportDataType.PRODUCTS: ["revenue", "units_sold", "cost"],
}
_KEY_COLUMN = {ImportDataType.FINANCIALS: None, ImportDataType.CUSTOMERS: "customer_id",
               ImportDataType.PRODUCTS: "product_id"}
MAX_STORED_VALUE = 1e13  # the database holds amounts up to 16 digits with 2 decimals


def _apply_storage_limits(data_type: ImportDataType, clean: pd.DataFrame, issues: List[ValidationIssueCreate]):
    """The validator keeps negative values (flagged) but the database only stores values >= 0.
    Such a value is stored as unknown (never as 0) and reported, so nothing changes silently."""
    clean = clean.copy()
    key = _KEY_COLUMN[data_type]
    reported = 0
    for col in _NUMERIC_COLUMNS[data_type]:
        if col not in clean.columns:
            continue
        values = pd.to_numeric(clean[col], errors="coerce")
        bad = (values < 0) | (values >= MAX_STORED_VALUE)
        for idx in clean.index[bad.fillna(False)]:
            if reported < MAX_ISSUE_ROWS:
                where = clean.at[idx, "period"] + (f", {clean.at[idx, key]}" if key else "")
                issues.append(ValidationIssueCreate(
                    severity=IssueSeverity.WARNING, code="value_not_stored", column=col,
                    message=f"'{col}' for {where} is negative or too large to store; it was saved as unknown (not 0)."))
                reported += 1
        clean.loc[bad.fillna(False), col] = float("nan")
    return clean


def process_upload(data_type: ImportDataType, content: bytes) -> ProcessedImport:
    df = read_csv(content)
    report = validate_table(df, data_type.value)
    issues = _issues(report)
    if not report.is_usable:
        return ProcessedImport(ImportStatus.FAILED, report.rows_in, 0, issues, [])
    clean = _apply_storage_limits(data_type, report.clean, issues)
    rows = _storage_rows(data_type, clean)
    status = ImportStatus.COMPLETED_WITH_WARNINGS if issues else ImportStatus.COMPLETED
    return ProcessedImport(status, report.rows_in, len(rows), issues, rows)
