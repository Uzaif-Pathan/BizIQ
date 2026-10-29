"""Consistent error responses for the whole API.

Every error is returned in this shape:

    {
      "error": {
        "code": "validation_error",
        "message": "Request validation failed.",
        "details": [{"field": "name", "message": "Field required", "type": "missing"}]
      }
    }
"""

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("biziq")


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
}


class AppError(Exception):
    """Raise this from services/routes for expected, user-facing errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: Optional[str] = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or _STATUS_CODES.get(status_code, "app_error")
        self.details = details


def error_response(
    status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(exc.status_code, code, message)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        details.append(
            {
                "field": ".".join(loc) or None,
                "message": str(err.get("msg", "Invalid value")),
                "type": str(err.get("type", "value_error")),
            }
        )
    return error_response(422, "validation_error", "Request validation failed.", details)


async def database_not_configured_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        503, "database_unavailable", "The database is not configured. Set DATABASE_URL and restart."
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from app.db.session import DatabaseNotConfigured

    app.add_exception_handler(DatabaseNotConfigured, database_not_configured_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
