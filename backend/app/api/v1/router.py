"""Version 1 API router. Add new endpoint modules here as they are built."""

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])

# Later (examples):
# from app.api.v1.endpoints import businesses
# api_router.include_router(businesses.router, prefix="/businesses", tags=["Businesses"])
