from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_business_repo
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
