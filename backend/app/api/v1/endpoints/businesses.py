from typing import List

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_analysis_repo, get_business_repo, get_import_repo
from app.core.errors import AppError
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate

router = APIRouter()


@router.post("", response_model=BusinessRead, status_code=201)
def create_business(data: BusinessCreate, repo=Depends(get_business_repo)):
    return repo.create(data)


@router.get("", response_model=List[BusinessRead])
def list_businesses(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repo=Depends(get_business_repo),
):
    return repo.list(limit=limit, offset=offset)


@router.get("/{business_id}", response_model=BusinessRead)
def get_business(business_id: int, repo=Depends(get_business_repo)):
    business = repo.get(business_id)
    if business is None:
        raise AppError("Business not found.", status_code=404)
    return business


@router.patch("/{business_id}", response_model=BusinessRead)
def update_business(
    business_id: int, data: BusinessUpdate, repo=Depends(get_business_repo)
):
    business = repo.update(business_id, data)
    if business is None:
        raise AppError("Business not found.", status_code=404)
    return business


@router.delete("/{business_id}", status_code=204)
def delete_business(
    business_id: int,
    repo=Depends(get_business_repo),
    analysis_repo=Depends(get_analysis_repo),
    import_repo=Depends(get_import_repo),
):
    deleted = repo.delete(business_id)
    if not deleted:
        raise AppError("Business not found.", status_code=404)

    # SQL repositories rely on the existing database ON DELETE CASCADE constraints.
    # In-memory storage keeps these records in separate repositories, so clean them up here.
    if hasattr(analysis_repo, "delete_for_business"):
        analysis_repo.delete_for_business(business_id)
    if hasattr(import_repo, "delete_for_business"):
        import_repo.delete_for_business(business_id)

    return Response(status_code=204)
