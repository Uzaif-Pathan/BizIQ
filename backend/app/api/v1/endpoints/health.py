from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


def health_payload() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "application": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env,
    }


@router.get("/health")
def health_check() -> dict:
    return health_payload()
