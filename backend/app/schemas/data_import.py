"""Data import records and validation issues."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import EntityId

FileName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ImportDataType(str, Enum):
    FINANCIALS = "financials"
    CUSTOMERS = "customers"
    PRODUCTS = "products"


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class DataImportCreate(BaseModel):
    """Metadata of an uploaded file. The file itself is never stored, only its validated rows."""

    data_type: ImportDataType
    file_name: FileName


class DataImportStatusUpdate(BaseModel):
    """Used by the import/validation service to report progress.

    Counts are null until known. Null means "not counted yet", not zero.
    """

    status: ImportStatus
    row_count: Optional[int] = Field(default=None, ge=0)
    valid_row_count: Optional[int] = Field(default=None, ge=0)
    error_count: Optional[int] = Field(default=None, ge=0)
    warning_count: Optional[int] = Field(default=None, ge=0)


class DataImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    business_id: EntityId
    data_type: ImportDataType
    file_name: str
    status: ImportStatus
    row_count: Optional[int] = None
    valid_row_count: Optional[int] = None
    error_count: Optional[int] = None
    warning_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ValidationIssueCreate(BaseModel):
    severity: IssueSeverity
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    row_number: Optional[int] = Field(default=None, ge=1)  # 1-based, null for file-level issues
    column: Optional[str] = Field(default=None, max_length=100)
    value: Optional[str] = Field(default=None, max_length=500)  # offending value as text


class ValidationIssueRead(ValidationIssueCreate):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    import_id: EntityId
    created_at: datetime
