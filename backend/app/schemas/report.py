"""Structured report payload. Rendering the report page is Person 1's job."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.analysis import AnalysisResult
from app.schemas.business import BusinessRead


class ReportPayload(BaseModel):
    business: BusinessRead
    analysis: AnalysisResult
    generated_at: datetime
