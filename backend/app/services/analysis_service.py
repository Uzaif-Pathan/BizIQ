"""Runs an analysis and stores its status, timestamps and result."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from analytics_engine.api_adapter import EngineRunFailed
from app.schemas.analysis import (
    AnalysisResult,
    AnalysisStatus,
    BenchmarkStatus,
    EvidenceLevel,
    Metrics,
)
from app.schemas.business import BusinessRead
from app.services.analytics_service import AnalyticsEngine

logger = logging.getLogger("biziq")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_result(
    analysis_id: str, business_id: str, status: AnalysisStatus, created_at: datetime, **extra
) -> AnalysisResult:
    """pending and failed runs still return all eight core fields (see contracts/README.md)."""
    return AnalysisResult(
        analysis_id=analysis_id,
        business_id=business_id,
        status=status,
        metrics=Metrics(),
        findings=[],
        recommendations=[],
        evidence_level=EvidenceLevel.INSUFFICIENT,
        benchmark_status=BenchmarkStatus.UNAVAILABLE,
        created_at=created_at,
        **extra,
    )


def run_analysis(business: BusinessRead, engine: AnalyticsEngine, analysis_repo, business_repo):
    analysis_id = str(uuid4())
    business_id = str(business.id)
    created_at = _now()

    # 1. Save the run as pending first, so history shows it even if the engine crashes.
    analysis_repo.save(
        _empty_result(analysis_id, business_id, AnalysisStatus.PENDING, created_at)
    )
    business_repo.set_latest_analysis_status(business.id, AnalysisStatus.PENDING)

    # 2. Run the engine. Any error becomes a failed run, never a server crash.
    try:
        output = engine(business)
        result = AnalysisResult(
            analysis_id=analysis_id,
            business_id=business_id,
            status=AnalysisStatus.COMPLETED,
            created_at=created_at,
            completed_at=_now(),
            **output,
        )
    except EngineRunFailed as exc:
        # Expected failure: the engine explains why (e.g. no usable financial data). The message is
        # written for users and contains no internal details, so it is safe to show.
        logger.info("Analysis %s could not run for business %s: %s", analysis_id, business_id, exc.code)
        result = _empty_result(
            analysis_id,
            business_id,
            AnalysisStatus.FAILED,
            created_at,
            completed_at=_now(),
            error_message=exc.message,
            error_code=exc.code,
        )
    except Exception:
        logger.exception("Analysis %s failed for business %s", analysis_id, business_id)
        result = _empty_result(
            analysis_id,
            business_id,
            AnalysisStatus.FAILED,
            created_at,
            completed_at=_now(),
            error_message="Analysis could not be completed. Please try again later.",
        )

    # 3. Save the final state.
    analysis_repo.save(result)
    business_repo.set_latest_analysis_status(business.id, result.status)
    return result
