"""Database engine and sessions, created on first use.

Nothing here connects at import time, so the API, /health and the tests start without a database.
A request that really needs the database gets a clear 503 error when DATABASE_URL is not set.
"""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseNotConfigured(RuntimeError):
    """DATABASE_URL is empty, so no database can be used."""


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured.")
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> "sessionmaker[Session]":
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


class _LazySessionLocal:
    """Drop-in for the old ``SessionLocal``: calling it returns a new Session."""

    def __call__(self) -> Session:
        return get_sessionmaker()()


SessionLocal = _LazySessionLocal()
