"""Upload a CSV, see how validation went, and list the problems found.

Processing happens during the upload request. A file that cannot be used still gets a record
(status "failed") with its issues, and returns 201, the same way a failed analysis does.
Files that cannot be read at all (empty, not UTF-8, too large, not .csv) return 400 or 413.
"""

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import get_business_repo, get_import_repo
from app.core.errors import AppError
from app.schemas.data_import import (
    DataImportRead,
    ImportDataType,
    IssueSeverity,
    ValidationIssueRead,
)
from app.services.import_service import MAX_FILE_BYTES, ImportFileError, process_upload

router = APIRouter()


def _require_business(business_id: int, business_repo) -> None:
    if business_repo.get(business_id) is None:
        raise AppError("Business not found.", status_code=404)


def _safe_name(name: Optional[str]) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1].strip()
    return re.sub(r"[\x00-\x1f]", "", name)[:255]


@router.post(
    "/businesses/{business_id}/imports", response_model=DataImportRead, status_code=201
)
def upload_import(
    business_id: int,
    data_type: ImportDataType = Form(...),
    file: UploadFile = File(...),
    business_repo=Depends(get_business_repo),
    import_repo=Depends(get_import_repo),
):
    """Upload financials, customers or products as a CSV file (UTF-8, max 5 MB)."""
    _require_business(business_id, business_repo)
    file_name = _safe_name(file.filename)
    if not file_name.lower().endswith(".csv"):
        raise AppError("Please upload a .csv file.", status_code=400)
    content = file.file.read(MAX_FILE_BYTES + 1)
    try:
        processed = process_upload(data_type, content)
    except ImportFileError as exc:
        raise AppError(exc.message, status_code=exc.status_code)
    return import_repo.save(business_id, file_name, data_type, processed)


@router.get("/businesses/{business_id}/imports", response_model=List[DataImportRead])
def list_imports(
    business_id: int,
    business_repo=Depends(get_business_repo),
    import_repo=Depends(get_import_repo),
):
    _require_business(business_id, business_repo)
    return import_repo.list_for_business(business_id)


@router.get(
    "/businesses/{business_id}/imports/{import_id}", response_model=DataImportRead
)
def get_import(
    business_id: int,
    import_id: int,
    business_repo=Depends(get_business_repo),
    import_repo=Depends(get_import_repo),
):
    _require_business(business_id, business_repo)
    item = import_repo.get(business_id, import_id)
    if item is None:
        raise AppError("Import not found.", status_code=404)
    return item


@router.get(
    "/businesses/{business_id}/imports/{import_id}/issues",
    response_model=List[ValidationIssueRead],
)
def list_import_issues(
    business_id: int,
    import_id: int,
    severity: Optional[IssueSeverity] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    business_repo=Depends(get_business_repo),
    import_repo=Depends(get_import_repo),
):
    _require_business(business_id, business_repo)
    issues = import_repo.list_issues(business_id, import_id, severity, limit, offset)
    if issues is None:
        raise AppError("Import not found.", status_code=404)
    return issues
