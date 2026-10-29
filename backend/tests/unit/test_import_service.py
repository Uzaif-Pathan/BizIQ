"""CSV reading, validation and row preparation for uploads (no web or database needed)."""
from datetime import date
from pathlib import Path

import pytest

from app.repositories.imports import InMemoryImportRepository
from app.schemas.data_import import ImportDataType, ImportStatus, IssueSeverity
from app.services.import_service import ImportFileError, process_upload

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def _read(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def test_clean_financials_complete_without_issues():
    p = process_upload(ImportDataType.FINANCIALS, _read("retail/financials.csv"))
    assert p.status == ImportStatus.COMPLETED
    assert p.rows_received == p.rows_accepted == 24 and p.issues == []
    assert p.rows[0] == {"period_start": date(2024, 1, 1), "revenue": 253047.0, "expenses": 191219.0,
                         "expenses_complete": True}


def test_customers_and_products_prepare_storage_rows():
    c = process_upload(ImportDataType.CUSTOMERS, _read("retail/customers.csv"))
    assert c.status == ImportStatus.COMPLETED and c.rows_accepted == 1022
    assert c.rows[0]["customer_ref"] == "C001" and isinstance(c.rows[0]["transactions"], int)
    p = process_upload(ImportDataType.PRODUCTS, _read("retail/products.csv"))
    assert p.status == ImportStatus.COMPLETED and p.rows_accepted == 168
    assert p.rows[0]["product_ref"] == "P01" and p.rows[0]["cost"] == 61014.64


def test_messy_file_keeps_good_rows_and_reports_every_problem():
    p = process_upload(ImportDataType.FINANCIALS, _read("messy/financials.csv"))
    assert p.status == ImportStatus.COMPLETED_WITH_WARNINGS
    assert (p.rows_received, p.rows_accepted) == (14, 9)
    codes = {i.code for i in p.issues}
    assert {"invalid_period", "conflicting_duplicates", "duplicate_rows", "invalid_numeric",
            "missing_values", "negative_value", "invalid_flag", "suspicious_outlier",
            "value_not_stored"} <= codes
    assert p.error_count > 0 and p.warning_count > 0
    assert all(i.row_number is None or i.row_number >= 1 for i in p.issues)


def test_unknown_stays_unknown_never_zero():
    p = process_upload(ImportDataType.FINANCIALS, _read("messy/financials.csv"))
    by_month = {r["period_start"].month: r for r in p.rows}
    assert by_month[5]["revenue"] is None      # "₹25,000" is not a number
    assert by_month[6]["revenue"] is None      # blank
    assert by_month[7]["revenue"] is None      # negative cannot be stored; unknown, not 0
    assert by_month[8]["expenses_complete"] is None  # "maybe" is not true/false
    assert by_month[1]["revenue"] == 100000.0


def test_missing_required_column_fails_and_stores_nothing():
    p = process_upload(ImportDataType.FINANCIALS, b"period,costs\n2025-01,5\n")
    assert p.status == ImportStatus.FAILED and p.rows == [] and p.rows_accepted == 0
    assert p.issues[0].code == "missing_required_columns"
    assert p.issues[0].severity == IssueSeverity.ERROR


def test_wrong_data_type_for_file_fails():
    p = process_upload(ImportDataType.CUSTOMERS, _read("retail/financials.csv"))
    assert p.status == ImportStatus.FAILED and p.rows == []


def test_header_only_file_fails():
    p = process_upload(ImportDataType.FINANCIALS, b"period,revenue\n")
    assert p.status == ImportStatus.FAILED


@pytest.mark.parametrize("content,status", [(b"", 400), (b"   \n", 400), (b"\xff\xfe\x00bad", 400)])
def test_unreadable_files_are_rejected(content, status):
    with pytest.raises(ImportFileError) as exc:
        process_upload(ImportDataType.FINANCIALS, content)
    assert exc.value.status_code == status


def test_too_large_file_is_rejected():
    with pytest.raises(ImportFileError) as exc:
        process_upload(ImportDataType.FINANCIALS, b"a" * (5 * 1024 * 1024 + 1))
    assert exc.value.status_code == 413


def test_utf8_bom_is_accepted():
    p = process_upload(ImportDataType.FINANCIALS, b"\xef\xbb\xbfperiod,revenue\n2025-01,10\n")
    assert p.status in (ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_WARNINGS) and p.rows_accepted == 1


def test_in_memory_repository_records_import_and_issues():
    repo = InMemoryImportRepository()
    p = process_upload(ImportDataType.FINANCIALS, _read("messy/financials.csv"))
    rec = repo.save(7, "messy.csv", ImportDataType.FINANCIALS, p)
    assert rec.id == 1 and rec.business_id == 7 and rec.status == ImportStatus.COMPLETED_WITH_WARNINGS
    assert (rec.row_count, rec.valid_row_count) == (14, 9)
    assert repo.get(7, rec.id) == rec and repo.get(8, rec.id) is None
    assert [i.id for i in repo.list_for_business(7)] == [1]
    errors = repo.list_issues(7, rec.id, IssueSeverity.ERROR)
    assert len(errors) == rec.error_count and all(i.severity == IssueSeverity.ERROR for i in errors)
    assert len(repo.list_issues(7, rec.id, limit=3, offset=1)) == 3
    assert repo.list_issues(8, rec.id) is None
