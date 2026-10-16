"""Structured validation results (never just printed messages)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

MAX_ROWS_LISTED = 20  # keep issue payloads small


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str  # stable machine-readable code
    message: str
    dataset: str | None = None
    column: str | None = None
    count: int | None = None
    rows: list[int] = field(default_factory=list)  # 0-based input row positions

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "dataset": self.dataset,
            "column": self.column,
            "count": self.count,
            "rows": self.rows[:MAX_ROWS_LISTED],
        }


@dataclass
class ValidationReport:
    dataset: str
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    clean: pd.DataFrame | None = None  # cleaned data; None if unusable
    rows_in: int = 0
    rows_out: int = 0

    @property
    def is_valid(self) -> bool:
        """True if validation raised no errors (warnings are allowed)."""
        return not self.errors

    @property
    def is_usable(self) -> bool:
        """True if at least one clean row remains, even when errors dropped others."""
        return self.clean is not None and len(self.clean) > 0

    def add(self, severity: str, code: str, message: str, *, column: str | None = None,
            rows: list[int] | None = None) -> None:
        rows = rows or []
        issue = Issue(severity, code, message, dataset=self.dataset, column=column,
                      count=len(rows) if rows else None, rows=rows)
        (self.errors if severity == "error" else self.warnings).append(issue)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe form (matches the ``validation`` block of the contract)."""
        return {
            "dataset": self.dataset,
            "is_valid": self.is_valid,
            "is_usable": self.is_usable,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
        }
