from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_repo, get_business_repo
from app.core.errors import AppError
from app.schemas.analysis import (
    AnalysisResult,
    AnalysisRunSummary,
    AnalysisStatus,
    Finding,
    Recommendation,
)
from app.schemas.report import ReportPayload
from app.services.analysis_service import run_analysis
from app.services.analytics_service import get_analytics_engine

router = APIRouter()


def _get_analysis_or_404(analysis_id: str, analysis_repo) -> AnalysisResult:
    result = analysis_repo.get(analysis_id)
    if result is None:
        raise AppError("Analysis not found.", status_code=404)
    return result


@router.post(
    "/businesses/{business_id}/analyses", response_model=AnalysisResult, status_code=201
)
def request_analysis(
    business_id: UUID,
    business_repo=Depends(get_business_repo),
    analysis_repo=Depends(get_analysis_repo),
    engine=Depends(get_analytics_engine),
):
    """Runs an analysis now. A failed run is still returned (status "failed") with a 201."""
    business = business_repo.get(business_id)
    if business is None:
        raise AppError("Business not found.", status_code=404)
    return run_analysis(business, engine, analysis_repo, business_repo)


@router.get(
    "/businesses/{business_id}/analyses", response_model=List[AnalysisRunSummary]
)
def list_analysis_history(
    business_id: UUID,
    business_repo=Depends(get_business_repo),
    analysis_repo=Depends(get_analysis_repo),
):
    if business_repo.get(business_id) is None:
        raise AppError("Business not found.", status_code=404)
    return analysis_repo.list_for_business(str(business_id))


@router.get("/analyses/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: str, analysis_repo=Depends(get_analysis_repo)):
    return _get_analysis_or_404(analysis_id, analysis_repo)


@router.get("/analyses/{analysis_id}/findings", response_model=List[Finding])
def get_findings(analysis_id: str, analysis_repo=Depends(get_analysis_repo)):
    return _get_analysis_or_404(analysis_id, analysis_repo).findings


@router.get(
    "/analyses/{analysis_id}/recommendations", response_model=List[Recommendation]
)
def get_recommendations(analysis_id: str, analysis_repo=Depends(get_analysis_repo)):
    return _get_analysis_or_404(analysis_id, analysis_repo).recommendations


@router.get("/analyses/{analysis_id}/report", response_model=ReportPayload)
def get_report(
    analysis_id: str,
    business_repo=Depends(get_business_repo),
    analysis_repo=Depends(get_analysis_repo),
):
    analysis = _get_analysis_or_404(analysis_id, analysis_repo)
    if analysis.status != AnalysisStatus.COMPLETED:
        raise AppError(
            "A report is available only for completed analyses.", status_code=409
        )
    business = business_repo.get(UUID(analysis.business_id))
    if business is None:
        raise AppError("Business not found.", status_code=404)
    return ReportPayload(
        business=business, analysis=analysis, generated_at=datetime.now(timezone.utc)
    )
