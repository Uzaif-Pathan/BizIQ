"""BizIQ API entry point.

Run from the backend/ folder:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import health_payload
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BizIQ API",
        version="0.1.0",
        description="Business intelligence and strategy platform",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Unversioned health check for quick smoke tests; /api/v1/health also exists.
    @app.get("/health", tags=["Health"])
    def root_health() -> dict:
        return health_payload()

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
