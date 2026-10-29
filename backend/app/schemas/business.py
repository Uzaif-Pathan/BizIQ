"""Business schemas: create, update and read."""

from datetime import datetime
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.schemas.analysis import AnalysisStatus
from app.schemas.common import EntityId

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Goal = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class BusinessType(str, Enum):
    RETAIL = "retail"
    SERVICE = "service"
    MANUFACTURING = "manufacturing"
    HYBRID = "hybrid"
    OTHER = "other"


class BusinessStage(str, Enum):
    """New businesses have limited data (cold start); established ones have history."""

    NEW = "new"
    ESTABLISHED = "established"


class BusinessBase(BaseModel):
    name: Name
    industry: ShortText
    business_type: BusinessType
    stage: BusinessStage = BusinessStage.ESTABLISHED
    city: Optional[ShortText] = None
    district: Optional[ShortText] = None
    state: Optional[ShortText] = None
    country: ShortText = "India"
    employee_count: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=1000)


class BusinessCreate(BusinessBase):
    goals: List[Goal] = Field(default_factory=list, max_length=20)


class BusinessUpdate(BaseModel):
    """Partial update. Send only the fields to change; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[Name] = None
    industry: Optional[ShortText] = None
    business_type: Optional[BusinessType] = None
    stage: Optional[BusinessStage] = None
    city: Optional[ShortText] = None
    district: Optional[ShortText] = None
    state: Optional[ShortText] = None
    country: Optional[ShortText] = None
    employee_count: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=1000)
    goals: Optional[List[Goal]] = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _check_update(self) -> "BusinessUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        # These columns are required, so they cannot be set to null.
        for field in ("name", "industry", "business_type", "stage", "country"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"'{field}' cannot be null.")
        return self


class BusinessRead(BusinessBase):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    goals: List[str] = Field(default_factory=list)
    # Shown on the My Businesses page. null means no analysis has been run yet.
    latest_analysis_status: Optional[AnalysisStatus] = None
    created_at: datetime
    updated_at: datetime
