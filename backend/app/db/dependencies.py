from collections.abc import Generator
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """One session per request. Raises a 503 error (via DatabaseNotConfigured) when no database is set."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_optional() -> Generator[Optional[Session], None, None]:
    """Like get_db, but yields None when DATABASE_URL is empty so the API can still run on in-memory
    storage (used for quick demos and for the tests)."""
    if not get_settings().database_url:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
