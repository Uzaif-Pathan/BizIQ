"""Uploads stored in PostgreSQL, and used by a real analysis (needs TEST_DATABASE_URL)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import func, select  # noqa: E402

from app.models import CustomerActivity, MonthlyFinancial, MonthlyProductMetric, ProductService  # noqa: E402
from app.repositories.imports import SqlImportRepository  # noqa: E402
from app.repositories.sql import SqlBusinessRepository  # noqa: E402
from app.schemas.business import BusinessCreate  # noqa: E402
from app.schemas.data_import import ImportDataType, ImportStatus, IssueSeverity  # noqa: E402
from app.services.data_loader import load_engine_data  # noqa: E402
from app.services.import_service import process_upload  # noqa: E402
from analytics_engine.api_adapter import run_for_service  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def _business(db):
    return SqlBusinessRepository(db).create(
        BusinessCreate(name="Upload Test", industry="Grocery", business_type="retail"))


def _import(db, business, data_type, path, name="f.csv"):
    processed = process_upload(data_type, (SAMPLES / path).read_bytes())
    return SqlImportRepository(db).save(business.id, name, data_type, processed)


def test_clean_upload_stores_rows_and_counts(db):
    b = _business(db)
    rec = _import(db, b, ImportDataType.FINANCIALS, "retail/financials.csv")
    assert rec.status == ImportStatus.COMPLETED and (rec.row_count, rec.valid_row_count) == (24, 24)
    assert db.scalar(select(func.count()).select_from(MonthlyFinancial)) == 24
    first = db.scalars(select(MonthlyFinancial).order_by(MonthlyFinancial.period_start)).first()
    assert first.period_start == date(2024, 1, 1) and first.revenue == Decimal("253047.00")
    assert first.source_import_id == rec.id and first.expenses_complete is True


def test_messy_upload_stores_unknown_as_null_and_keeps_issues(db):
    b = _business(db)
    repo = SqlImportRepository(db)
    rec = _import(db, b, ImportDataType.FINANCIALS, "messy/financials.csv", "messy.csv")
    assert rec.status == ImportStatus.COMPLETED_WITH_WARNINGS and rec.valid_row_count == 9
    rows = {m.period_start.month: m for m in db.scalars(select(MonthlyFinancial))}
    assert len(rows) == 9
    assert rows[5].revenue is None and rows[6].revenue is None and rows[7].revenue is None
    assert rows[8].expenses_complete is None
    issues = repo.list_issues(b.id, rec.id)
    assert len(issues) == rec.error_count + rec.warning_count
    assert all(i.severity == IssueSeverity.ERROR for i in repo.list_issues(b.id, rec.id, IssueSeverity.ERROR))
    assert repo.get(b.id, rec.id).status == ImportStatus.COMPLETED_WITH_WARNINGS
    assert repo.get(b.id + 1, rec.id) is None and repo.list_issues(b.id + 1, rec.id) is None


def test_failed_upload_stores_no_rows(db):
    b = _business(db)
    processed = process_upload(ImportDataType.FINANCIALS, b"period,costs\n2025-01,5\n")
    rec = SqlImportRepository(db).save(b.id, "bad.csv", ImportDataType.FINANCIALS, processed)
    assert rec.status == ImportStatus.FAILED and rec.valid_row_count == 0
    assert db.scalar(select(func.count()).select_from(MonthlyFinancial)) == 0
    assert SqlImportRepository(db).list_issues(b.id, rec.id)[0].code == "missing_required_columns"


def test_uploading_again_replaces_the_same_months(db):
    b = _business(db)
    _import(db, b, ImportDataType.FINANCIALS, "retail/financials.csv")
    again = process_upload(ImportDataType.FINANCIALS, b"period,revenue,expenses\n2024-01,1000,400\n")
    SqlImportRepository(db).save(b.id, "fix.csv", ImportDataType.FINANCIALS, again)
    assert db.scalar(select(func.count()).select_from(MonthlyFinancial)) == 24
    jan = db.scalars(select(MonthlyFinancial).where(MonthlyFinancial.period_start == date(2024, 1, 1))).one()
    assert jan.revenue == Decimal("1000.00") and jan.other_expenses == Decimal("400.00")
    assert jan.expenses_complete is None  # not stated in the new file


def test_customers_and_products_upload(db):
    b = _business(db)
    _import(db, b, ImportDataType.CUSTOMERS, "retail/customers.csv")
    _import(db, b, ImportDataType.PRODUCTS, "retail/products.csv")
    assert db.scalar(select(func.count()).select_from(CustomerActivity)) == 1022
    assert db.scalar(select(func.count()).select_from(MonthlyProductMetric)) == 168
    skus = set(db.scalars(select(ProductService.sku)))
    assert "P01" in skus
    _import(db, b, ImportDataType.PRODUCTS, "retail/products.csv")  # same file again: no duplicates
    assert db.scalar(select(func.count()).select_from(ProductService)) == len(skus)
    assert db.scalar(select(func.count()).select_from(MonthlyProductMetric)) == 168


def test_uploaded_data_feeds_a_real_analysis(db):
    b = _business(db)
    _import(db, b, ImportDataType.FINANCIALS, "retail/financials.csv")
    _import(db, b, ImportDataType.CUSTOMERS, "retail/customers.csv")
    _import(db, b, ImportDataType.PRODUCTS, "retail/products.csv")
    output = run_for_service(b, load_engine_data(db, int(b.id)))
    assert output["metrics"]["revenue"] == 3726825.0  # same total as the seeded demo store (same CSV files)
