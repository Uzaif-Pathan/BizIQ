from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_business_repo
from app.core.errors import AppError
from app.db.dependencies import get_db_optional
from app.schemas.benchmark import BenchmarkResponse
from app.services.benchmark_service import CONTEXT_NOTE, load_candidate_rows, select_benchmarks

router = APIRouter()


@router.get("/businesses/{business_id}/benchmarks", response_model=BenchmarkResponse)
def get_business_benchmarks(
    business_id: int,
    business_repo=Depends(get_business_repo),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Survey context for this business (value added and pay), with source, year and the geography level
    actually used. Returns status "unavailable" when no benchmark data exists. Context only: these numbers
    are not profit margins and are never fed into the analysis."""
    business = business_repo.get(business_id)
    if business is None:
        raise AppError("Business not found.", status_code=404)
    if db is None:
        payload = {"status": "unavailable", "items": [], "matched_industry": None, "matched_state": None,
                   "levels_tried": ["district", "state", "region", "national"],
                   "notes": ["No database is configured, so no benchmark data is available.", CONTEXT_NOTE]}
    else:
        payload = select_benchmarks(
            load_candidate_rows(db),
            {"industry": business.industry, "business_type": getattr(business.business_type, "value", business.business_type),
             "state": business.state, "district": business.district},
        )
    return {"business_id": str(business.id), **payload}
