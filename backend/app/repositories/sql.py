"""PostgreSQL versions of the two repositories. Same method names as the in-memory ones, so the
routes did not change. Each request gets its own session (see app/api/deps.py)."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    AnalysisFinding,
    AnalysisRun,
    Business,
    BusinessGoal,
    Recommendation,
)
from app.schemas.analysis import (
    AnalysisResult,
    AnalysisRunSummary,
    AnalysisStatus,
    EvidenceLevel,
)
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _value(x):
    return x.value if isinstance(x, Enum) else x


_RUN_TO_STATUS = {
    "PENDING": AnalysisStatus.PENDING,
    "RUNNING": AnalysisStatus.PENDING,
    "COMPLETED": AnalysisStatus.COMPLETED,
    "FAILED": AnalysisStatus.FAILED,
}
_STATUS_TO_RUN = {
    AnalysisStatus.PENDING: "PENDING",
    AnalysisStatus.COMPLETED: "COMPLETED",
    AnalysisStatus.FAILED: "FAILED",
}
_ROW_FIELDS = {  # API field -> Business column
    "name": "business_name",
    "industry": "industry_name",
    "business_type": "business_type",
    "stage": "stage",
    "description": "description",
    "city": "city",
    "district": "district",
    "state": "state",
    "country": "country",
    "employee_count": "employee_count",
}


class SqlBusinessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- helpers -----------------------------------------------------------------------------
    def _goals(self, business_id: int) -> List[str]:
        stmt = (
            select(BusinessGoal.description)
            .where(BusinessGoal.business_id == business_id, BusinessGoal.status == "ACTIVE")
            .order_by(BusinessGoal.goal_id)
        )
        return [g for g in self.db.scalars(stmt) if g]

    def _latest_status(self, business_id: int) -> Optional[AnalysisStatus]:
        stmt = (
            select(AnalysisRun.run_status)
            .where(AnalysisRun.business_id == business_id)
            .order_by(AnalysisRun.started_at.desc(), AnalysisRun.analysis_id.desc())
            .limit(1)
        )
        status = self.db.scalar(stmt)
        return _RUN_TO_STATUS.get(status) if status else None

    def _to_read(self, row: Business) -> BusinessRead:
        return BusinessRead(
            id=row.business_id,
            name=row.business_name,
            industry=row.industry_name or "",
            business_type=row.business_type or "other",
            stage=row.stage,
            description=row.description,
            city=row.city,
            district=row.district,
            state=row.state,
            country=row.country,
            employee_count=row.employee_count,
            goals=self._goals(row.business_id),
            latest_analysis_status=self._latest_status(row.business_id),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _replace_goals(self, business_id: int, goals: List[str]) -> None:
        self.db.execute(delete(BusinessGoal).where(BusinessGoal.business_id == business_id))
        for text in goals:
            self.db.add(BusinessGoal(business_id=business_id, goal_type="GENERAL", description=text, status="ACTIVE"))

    # -- repository methods --------------------------------------------------------------------
    def create(self, data: BusinessCreate) -> BusinessRead:
        row = Business(
            owner_user_id=get_settings().default_owner_user_id,
            business_name=data.name,
            industry_name=data.industry,
            business_type=_value(data.business_type),
            stage=_value(data.stage),
            description=data.description,
            city=data.city,
            district=data.district,
            state=data.state,
            country=data.country,
            employee_count=data.employee_count,
        )
        self.db.add(row)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                "The default owner user does not exist. Run scripts/seed_demo_data.py first.",
                status_code=500,
                code="owner_missing",
            ) from exc
        self._replace_goals(row.business_id, list(data.goals))
        self.db.commit()
        self.db.refresh(row)
        return self._to_read(row)

    def list(self, limit: int = 50, offset: int = 0) -> List[BusinessRead]:
        stmt = (
            select(Business)
            .order_by(Business.created_at.desc(), Business.business_id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_read(r) for r in self.db.scalars(stmt)]

    def get(self, business_id: int) -> Optional[BusinessRead]:
        row = self.db.get(Business, business_id)
        return self._to_read(row) if row else None

    def update(self, business_id: int, data: BusinessUpdate) -> Optional[BusinessRead]:
        row = self.db.get(Business, business_id)
        if row is None:
            return None
        changes = data.model_dump(exclude_unset=True)
        goals = changes.pop("goals", None)
        for field, value in changes.items():
            setattr(row, _ROW_FIELDS[field], _value(value))
        if goals is not None:
            self._replace_goals(business_id, list(goals))
        row.updated_at = _now()
        self.db.commit()
        self.db.refresh(row)
        return self._to_read(row)

    def set_latest_analysis_status(self, business_id: int, status: AnalysisStatus) -> None:
        """Nothing to store: the latest status is read from the newest analysis run."""
        return None


def _availability_mode(result: AnalysisResult) -> str:
    cov = result.data_coverage or {}
    has = {k: cov.get(k) is not None for k in ("financials", "customers", "products")}
    if has["financials"] and has["customers"] and has["products"]:
        return "RICH"
    if has["financials"] and (has["customers"] or has["products"]):
        return "STANDARD"
    return "COLD_START"


def _score(result: AnalysisResult) -> Optional[Decimal]:
    score = (result.health_score or {}).get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 100:
        return Decimal(str(round(score, 2)))
    return None


class SqlAnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _row(self, public_id: str) -> Optional[AnalysisRun]:
        return self.db.scalar(select(AnalysisRun).where(AnalysisRun.public_id == public_id))

    def save(self, result: AnalysisResult) -> AnalysisResult:
        row = self._row(result.analysis_id)
        if row is None:
            row = AnalysisRun(
                public_id=result.analysis_id,
                business_id=int(result.business_id),
                availability_mode="COLD_START",
                evidence_level="INSUFFICIENT",
            )
            self.db.add(row)
        row.run_status = _STATUS_TO_RUN[result.status]
        row.availability_mode = _availability_mode(result)
        row.evidence_level = result.evidence_level.value.upper()
        row.viability_score = _score(result)
        row.benchmark_status = result.benchmark_status.value
        row.limitations = "\n".join(result.limitations) if result.limitations else None
        row.error_message = result.error_message
        row.started_at = result.created_at or _now()
        row.completed_at = result.completed_at
        row.result_json = result.model_dump(mode="json")
        self.db.flush()
        self._replace_findings_and_recommendations(row, result)
        self.db.commit()
        return result

    def _replace_findings_and_recommendations(self, row: AnalysisRun, result: AnalysisResult) -> None:
        self.db.execute(delete(AnalysisFinding).where(AnalysisFinding.analysis_id == row.analysis_id))
        self.db.execute(delete(Recommendation).where(Recommendation.analysis_id == row.analysis_id))
        if result.status != AnalysisStatus.COMPLETED:
            return
        level = result.evidence_level.value.upper()
        level = level if level in ("HIGH", "MEDIUM", "LOW") else "LOW"
        for f in result.findings:
            self.db.add(AnalysisFinding(
                analysis_id=row.analysis_id,
                category=f.category.value,
                metric_name=f.metric_name or f.finding_id,
                metric_value=Decimal(str(f.metric_value)) if f.metric_value is not None else None,
                evidence_level=level,
                explanation=f.description,
            ))
        for r in result.recommendations:
            self.db.add(Recommendation(
                analysis_id=row.analysis_id,
                external_id=r.recommendation_id,
                title=r.title[:250],
                description=r.action,
                priority=r.priority.value.upper(),
                evidence_strength=level,
                rationale=r.reason,
                kpi_name=(r.kpi or None) and r.kpi[:120],
            ))

    def get(self, analysis_id: str) -> Optional[AnalysisResult]:
        row = self._row(analysis_id)
        if row is None or row.result_json is None:
            return None
        return AnalysisResult.model_validate(row.result_json)

    def list_for_business(self, business_id: str) -> List[AnalysisRunSummary]:
        try:
            bid = int(business_id)
        except ValueError:
            return []
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.business_id == bid)
            .order_by(AnalysisRun.started_at.desc(), AnalysisRun.analysis_id.desc())
        )
        return [
            AnalysisRunSummary(
                analysis_id=r.public_id,
                business_id=str(r.business_id),
                status=_RUN_TO_STATUS[r.run_status],
                evidence_level=EvidenceLevel(r.evidence_level.lower()),
                method_version=(r.result_json or {}).get("method_version"),
                created_at=r.started_at,
                completed_at=r.completed_at,
            )
            for r in self.db.scalars(stmt)
        ]
