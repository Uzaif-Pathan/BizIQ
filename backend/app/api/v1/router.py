"""Version 1 API router. Add new endpoint modules here as they are built."""

from fastapi import APIRouter

from app.api.v1.endpoints import analyses, businesses, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(businesses.router, prefix="/businesses", tags=["Businesses"])
api_router.include_router(analyses.router, tags=["Analyses"])
