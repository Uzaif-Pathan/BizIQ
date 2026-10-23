"""Analysis result contract shared by the frontend, analytics engine and API.

The JSON form of this contract lives in contracts/analysis-result.schema.json.
If you change a field here, change it there too (and tell the whole team).

Conventions
-----------
* Money is a plain number in INR, never a formatted string.
* Percentages (e.g. profit_margin) are numbers in percent: 23.29 means 23.29 %.
* A metric that cannot be calculated is null. It is never silently 0.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceLevel(str, Enum):
    """How much data supports the analysis. Exact rules: documented by the analytics owner."""

    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BenchmarkStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class FindingCategory(str, Enum):
    FINANCIAL = "financial"
    CUSTOMER = "customer"
    PRODUCT = "product"
    TREND = "trend"
    BENCHMARK = "benchmark"
    DATA_QUALITY = "data_quality"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImpactDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


class Metrics(BaseModel):
    """Headline metrics. Every value may be null when it cannot be calculated.

    Extra metrics (for example revenue_growth_mom) are allowed so the analytics
    engine can add values without a schema change. They must be number or null.
    """

    model_config = ConfigDict(extra="allow")

    revenue: Optional[float] = None
    expenses: Optional[float] = None
    profit: Optional[float] = None
    profit_margin: Optional[float] = None  # percent


class Finding(BaseModel):
    finding_id: str
    category: FindingCategory
    title: str
    description: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    severity: Severity = Severity.INFO
    evidence: List[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    recommendation_id: str
    title: str
    issue: str
    reason: str  # why this recommendation was generated
    action: str
    priority: Priority
    # Every recommendation must point at the findings that triggered it.
    supporting_finding_ids: List[str] = Field(min_length=1)
    evidence: List[str] = Field(default_factory=list)
    kpi: Optional[str] = None
    expected_direction: Optional[ImpactDirection] = None


class AnalysisResult(BaseModel):
    """The standard analysis response. All eight core fields are always present."""

    # Plain strings: sample data uses ids like "sample-analysis-001".
    # Real ids are UUID strings.
    analysis_id: str
    business_id: str
    status: AnalysisStatus
    metrics: Metrics
    findings: List[Finding]
    recommendations: List[Recommendation]
    evidence_level: EvidenceLevel
    benchmark_status: BenchmarkStatus

    # Optional extras (not part of the eight core fields).
    method_version: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _failed_needs_message(self) -> "AnalysisResult":
        if self.status == AnalysisStatus.FAILED and not self.error_message:
            raise ValueError("error_message is required when status is 'failed'")
        return self


class AnalysisRunSummary(BaseModel):
    """One row of the Analysis History page."""

    model_config = ConfigDict(from_attributes=True)

    analysis_id: str
    business_id: str
    status: AnalysisStatus
    evidence_level: Optional[EvidenceLevel] = None
    method_version: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
