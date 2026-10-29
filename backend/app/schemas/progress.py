"""Progress on a recommendation (what the business owner did about it)."""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import EntityId


class ProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class ProgressUpdate(BaseModel):
    status: ProgressStatus
    note: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]] = None
    # A measured result for the recommendation's KPI. Leave out when not measured (never send 0 for "unknown").
    measured_value: Optional[float] = Field(default=None, allow_inf_nan=False, gt=-1e15, lt=1e15)
    due_date: Optional[date] = None


class ProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    recommendation_id: str  # the id shown in the analysis result, for example "REC-LOSS"
    status: ProgressStatus
    note: Optional[str] = None
    measured_value: Optional[float] = None
    due_date: Optional[date] = None
    updated_at: datetime
