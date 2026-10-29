"""Storage for data imports, their validation issues and the validated rows.

``InMemoryImportRepository`` (no DATABASE_URL): records the import and its issues but does NOT keep the
rows, so analyses cannot use them. It exists so the API runs and can be tested without a database.
``SqlImportRepository``: also writes the rows into monthly_financials / customer_activity /
products_services / monthly_product_metrics. A later upload replaces the months it contains (same
month, same customer or product); other months are left alone.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.schemas.data_import import (
    DataImportRead,
    ImportDataType,
    ImportStatus,
    IssueSeverity,
    ValidationIssueRead,
)
from app.services.import_service import ProcessedImport


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _filter_issues(issues: List[ValidationIssueRead], severity, limit: int, offset: int):
    if severity is not None:
        issues = [i for i in issues if i.severity == severity]
    return issues[offset : offset + limit]


class InMemoryImportRepository:
    def __init__(self) -> None:
        self._imports: Dict[int, DataImportRead] = {}
        self._issues: Dict[int, List[ValidationIssueRead]] = {}
        self._next_id = 1
        self._next_issue_id = 1

    def save(self, business_id: int, file_name: str, data_type: ImportDataType,
             processed: ProcessedImport) -> DataImportRead:
        now = _now()
        record = DataImportRead(
            id=self._next_id, business_id=business_id, data_type=data_type, file_name=file_name,
            status=processed.status, row_count=processed.rows_received,
            valid_row_count=processed.rows_accepted, error_count=processed.error_count,
            warning_count=processed.warning_count, created_at=now, updated_at=now,
        )
        issues = []
        for issue in processed.issues:
            issues.append(ValidationIssueRead(id=self._next_issue_id, import_id=record.id, created_at=now,
                                              **issue.model_dump()))
            self._next_issue_id += 1
        self._imports[record.id] = record
        self._issues[record.id] = issues
        self._next_id += 1
        return record

    def delete_for_business(self, business_id: int) -> None:
        """Delete in-memory import records and their validation issues for a business."""
        import_ids = [
            import_id for import_id, item in self._imports.items()
            if item.business_id == business_id
        ]
        for import_id in import_ids:
            self._imports.pop(import_id, None)
            self._issues.pop(import_id, None)

    def get(self, business_id: int, import_id: int) -> Optional[DataImportRead]:
        item = self._imports.get(import_id)
        return item if item is not None and item.business_id == business_id else None

    def list_for_business(self, business_id: int) -> List[DataImportRead]:
        items = [i for i in self._imports.values() if i.business_id == business_id]
        return sorted(items, key=lambda i: i.id, reverse=True)

    def list_issues(self, business_id: int, import_id: int, severity: Optional[IssueSeverity] = None,
                    limit: int = 100, offset: int = 0) -> Optional[List[ValidationIssueRead]]:
        if self.get(business_id, import_id) is None:
            return None
        return _filter_issues(self._issues.get(import_id, []), severity, limit, offset)


# ---------------------------------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------------------------------

def _dec(v: Optional[float]) -> Optional[Decimal]:
    return None if v is None else Decimal(str(round(float(v), 2)))


_DB_STATUS = {
    ImportStatus.PENDING: "PENDING",
    ImportStatus.PROCESSING: "PROCESSING",
    ImportStatus.COMPLETED: "COMPLETED",
    ImportStatus.COMPLETED_WITH_WARNINGS: "COMPLETED",  # derived again from the stored issues on read
    ImportStatus.FAILED: "FAILED",
}


class SqlImportRepository:
    def __init__(self, db) -> None:
        self.db = db

    # ---- writing ----
    def save(self, business_id: int, file_name: str, data_type: ImportDataType,
             processed: ProcessedImport) -> DataImportRead:
        from app.models import DataImport, ValidationIssue

        now = _now()
        try:
            row = DataImport(
                business_id=business_id, data_type=data_type.value.upper(), file_name=file_name[:255],
                file_format="csv", source_type="USER_UPLOAD", import_status=_DB_STATUS[processed.status],
                rows_received=processed.rows_received, rows_accepted=processed.rows_accepted,
                rows_rejected=max(processed.rows_received - processed.rows_accepted, 0),
                uploaded_at=now, completed_at=now,
            )
            self.db.add(row)
            self.db.flush()
            for issue in processed.issues:
                self.db.add(ValidationIssue(
                    import_id=row.import_id, row_number=issue.row_number, column_name=issue.column,
                    issue_type=issue.code[:60], severity=issue.severity.value.upper(),
                    issue_message=issue.message, resolution_status="OPEN",
                ))
            if processed.status != ImportStatus.FAILED and processed.rows:
                self._store_rows(business_id, row.import_id, data_type, processed.rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(business_id, row.import_id)

    def _store_rows(self, business_id: int, import_id: int, data_type: ImportDataType,
                    rows: List[Dict[str, Any]]) -> None:
        if data_type == ImportDataType.FINANCIALS:
            self._store_financials(business_id, import_id, rows)
        elif data_type == ImportDataType.CUSTOMERS:
            self._store_customers(business_id, import_id, rows)
        else:
            self._store_products(business_id, import_id, rows)

    def _store_financials(self, business_id, import_id, rows):
        from sqlalchemy import select

        from app.models import MonthlyFinancial

        periods = [r["period_start"] for r in rows]
        existing = {
            m.period_start: m for m in self.db.scalars(
                select(MonthlyFinancial).where(MonthlyFinancial.business_id == business_id,
                                               MonthlyFinancial.period_start.in_(periods)))
        }
        for r in rows:
            values = dict(revenue=_dec(r["revenue"]), fixed_expenses=None, variable_expenses=None,
                          other_expenses=_dec(r["expenses"]), expenses_complete=r["expenses_complete"],
                          source_import_id=import_id)
            m = existing.get(r["period_start"])
            if m is None:
                self.db.add(MonthlyFinancial(business_id=business_id, period_start=r["period_start"], **values))
            else:
                for k, v in values.items():
                    setattr(m, k, v)

    def _store_customers(self, business_id, import_id, rows):
        from sqlalchemy import select

        from app.models import CustomerActivity

        periods = {r["period_start"] for r in rows}
        existing = {
            (c.customer_ref, c.period_start): c for c in self.db.scalars(
                select(CustomerActivity).where(CustomerActivity.business_id == business_id,
                                               CustomerActivity.period_start.in_(periods)))
        }
        for r in rows:
            values = dict(transactions=r["transactions"], amount_spent=_dec(r["amount_spent"]),
                          source_import_id=import_id)
            c = existing.get((r["customer_ref"], r["period_start"]))
            if c is None:
                self.db.add(CustomerActivity(business_id=business_id, customer_ref=r["customer_ref"],
                                             period_start=r["period_start"], **values))
            else:
                for k, v in values.items():
                    setattr(c, k, v)

    def _store_products(self, business_id, import_id, rows):
        from sqlalchemy import select

        from app.models import MonthlyProductMetric, ProductService

        refs = {r["product_ref"] for r in rows}
        items = {
            p.sku: p for p in self.db.scalars(
                select(ProductService).where(ProductService.business_id == business_id,
                                             ProductService.sku.in_(refs)))
        }
        for r in rows:
            ref = r["product_ref"]
            if ref not in items:
                items[ref] = ProductService(business_id=business_id, item_name=(r["product_name"] or ref)[:200],
                                            item_type="PRODUCT", sku=ref[:100])
                self.db.add(items[ref])
            elif r["product_name"]:
                items[ref].item_name = r["product_name"][:200]
        self.db.flush()
        ids = [p.product_id for p in items.values()]
        periods = {r["period_start"] for r in rows}
        existing = {
            (m.product_id, m.period_start): m for m in self.db.scalars(
                select(MonthlyProductMetric).where(MonthlyProductMetric.product_id.in_(ids),
                                                   MonthlyProductMetric.period_start.in_(periods)))
        }
        for r in rows:
            pid = items[r["product_ref"]].product_id
            values = dict(units_sold=r["units_sold"], total_revenue=_dec(r["revenue"]),
                          total_cost=_dec(r["cost"]), source_import_id=import_id)
            m = existing.get((pid, r["period_start"]))
            if m is None:
                self.db.add(MonthlyProductMetric(product_id=pid, period_start=r["period_start"], **values))
            else:
                for k, v in values.items():
                    setattr(m, k, v)

    # ---- reading ----
    def _counts(self, import_ids: List[int]) -> Dict[int, Dict[str, int]]:
        from sqlalchemy import func, select

        from app.models import ValidationIssue

        counts: Dict[int, Dict[str, int]] = {i: {"ERROR": 0, "WARNING": 0} for i in import_ids}
        if import_ids:
            stmt = (select(ValidationIssue.import_id, ValidationIssue.severity, func.count())
                    .where(ValidationIssue.import_id.in_(import_ids))
                    .group_by(ValidationIssue.import_id, ValidationIssue.severity))
            for import_id, severity, n in self.db.execute(stmt):
                counts.setdefault(import_id, {"ERROR": 0, "WARNING": 0})[severity] = n
        return counts

    def _to_read(self, row, counts: Dict[str, int]) -> DataImportRead:
        errors, warnings = counts.get("ERROR", 0), counts.get("WARNING", 0)
        status = ImportStatus(row.import_status.lower())
        if status == ImportStatus.COMPLETED and (errors or warnings):
            status = ImportStatus.COMPLETED_WITH_WARNINGS
        return DataImportRead(
            id=row.import_id, business_id=row.business_id, data_type=ImportDataType(row.data_type.lower()),
            file_name=row.file_name, status=status, row_count=row.rows_received,
            valid_row_count=row.rows_accepted, error_count=errors, warning_count=warnings,
            created_at=row.uploaded_at, updated_at=row.completed_at or row.uploaded_at,
        )

    def get(self, business_id: int, import_id: int) -> Optional[DataImportRead]:
        from sqlalchemy import select

        from app.models import DataImport

        row = self.db.scalar(select(DataImport).where(DataImport.import_id == import_id,
                                                      DataImport.business_id == business_id))
        return None if row is None else self._to_read(row, self._counts([row.import_id])[row.import_id])

    def list_for_business(self, business_id: int) -> List[DataImportRead]:
        from sqlalchemy import select

        from app.models import DataImport

        rows = list(self.db.scalars(select(DataImport).where(DataImport.business_id == business_id)
                                    .order_by(DataImport.import_id.desc())))
        counts = self._counts([r.import_id for r in rows])
        return [self._to_read(r, counts[r.import_id]) for r in rows]

    def list_issues(self, business_id: int, import_id: int, severity: Optional[IssueSeverity] = None,
                    limit: int = 100, offset: int = 0) -> Optional[List[ValidationIssueRead]]:
        from sqlalchemy import select

        from app.models import ValidationIssue

        if self.get(business_id, import_id) is None:
            return None
        stmt = select(ValidationIssue).where(ValidationIssue.import_id == import_id)
        if severity is not None:
            stmt = stmt.where(ValidationIssue.severity == severity.value.upper())
        stmt = stmt.order_by(ValidationIssue.severity, ValidationIssue.issue_id).limit(limit).offset(offset)
        return [
            ValidationIssueRead(
                id=i.issue_id, import_id=i.import_id, severity=IssueSeverity(i.severity.lower()),
                code=i.issue_type, message=i.issue_message, row_number=i.row_number, column=i.column_name,
                value=None, created_at=i.created_at,
            )
            for i in self.db.scalars(stmt)
        ]
