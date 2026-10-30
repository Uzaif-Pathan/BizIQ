"""Benchmark context shown next to a business. Never used inside the analysis calculations."""

from typing import List, Optional

from pydantic import BaseModel


class BenchmarkItem(BaseModel):
    metric: str
    label: str
    definition: str
    value: float
    unit: Optional[str] = None
    geography_level_used: str  # state | national (district and region are tried first but have no data)
    geography: str
    industry_used: str
    sector: Optional[str] = None
    establishment_type: Optional[str] = None
    worker_group: Optional[str] = None
    year: int
    source: str
    note: Optional[str] = None
    # How narrow the comparison group is: all_industries | broad_sector | detailed_activity.
    # State rows are only broad sectors; detailed activities exist only nationally.
    specificity: str = "detailed_activity"
    specificity_note: Optional[str] = None


class MatchedIndustry(BaseModel):
    broad_sector: str
    activity: str
    match: str  # keyword | business_type | none


class BenchmarkResponse(BaseModel):
    business_id: str
    status: str  # available | partial | unavailable
    items: List[BenchmarkItem]
    matched_industry: Optional[MatchedIndustry] = None
    matched_state: Optional[str] = None
    levels_tried: List[str]
    notes: List[str]
