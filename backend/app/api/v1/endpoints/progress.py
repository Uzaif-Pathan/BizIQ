"""Record and read progress on the recommendations of an analysis."""

from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_repo, get_progress_repo
from app.core.errors import AppError
from app.schemas.progress import ProgressRead, ProgressUpdate

router = APIRouter()


def _require_recommendation(analysis_id: str, recommendation_id: str, analysis_repo) -> None:
    analysis = analysis_repo.get(analysis_id)
    if analysis is None:
        raise AppError("Analysis not found.", status_code=404)
    if recommendation_id not in {r.recommendation_id for r in analysis.recommendations}:
        raise AppError("Recommendation not found in this analysis.", status_code=404)


@router.get("/analyses/{analysis_id}/progress", response_model=List[ProgressRead])
def latest_progress(
    analysis_id: str,
    analysis_repo=Depends(get_analysis_repo),
    progress_repo=Depends(get_progress_repo),
):
    """Current progress of every recommendation that has had an update (recommendations never updated are not listed)."""
    if analysis_repo.get(analysis_id) is None:
        raise AppError("Analysis not found.", status_code=404)
    return progress_repo.latest(analysis_id)


@router.post(
    "/analyses/{analysis_id}/recommendations/{recommendation_id}/progress",
    response_model=ProgressRead,
    status_code=201,
)
def record_progress(
    analysis_id: str,
    recommendation_id: str,
    data: ProgressUpdate,
    analysis_repo=Depends(get_analysis_repo),
    progress_repo=Depends(get_progress_repo),
):
    _require_recommendation(analysis_id, recommendation_id, analysis_repo)
    item = progress_repo.record(analysis_id, recommendation_id, data)
    if item is None:
        raise AppError("Recommendation not found in this analysis.", status_code=404)
    return item


@router.get(
    "/analyses/{analysis_id}/recommendations/{recommendation_id}/progress",
    response_model=List[ProgressRead],
)
def progress_history(
    analysis_id: str,
    recommendation_id: str,
    analysis_repo=Depends(get_analysis_repo),
    progress_repo=Depends(get_progress_repo),
):
    """All updates for one recommendation, newest first."""
    _require_recommendation(analysis_id, recommendation_id, analysis_repo)
    return progress_repo.history(analysis_id, recommendation_id)
