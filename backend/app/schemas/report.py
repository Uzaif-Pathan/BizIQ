"""Structured report payload. Rendering the report page is Person 1's job."""

from datetime import datetime

from typing import List

from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisResult
from app.schemas.business import BusinessRead
from app.schemas.progress import ProgressRead


class ReportPayload(BaseModel):
    business: BusinessRead
    analysis: AnalysisResult
    generated_at: datetime
    # Latest update per recommendation that has one; recommendations never updated are not listed.
    recommendation_progress: List[ProgressRead] = Field(default_factory=list)
