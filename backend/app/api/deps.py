"""FastAPI dependencies.

With DATABASE_URL set, requests use the PostgreSQL repositories (one session per request).
Without it, the in-memory repositories are used so the API still starts; data is then lost on restart.
"""

import logging
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_optional
from app.repositories.imports import InMemoryImportRepository, SqlImportRepository
from app.repositories.progress import InMemoryProgressRepository, SqlProgressRepository
from app.repositories.memory import (
    InMemoryAnalysisRepository,
    InMemoryBusinessRepository,
)
from app.repositories.sql import SqlAnalysisRepository, SqlBusinessRepository

logger = logging.getLogger("biziq")

_business_repo = InMemoryBusinessRepository()
_analysis_repo = InMemoryAnalysisRepository()
_import_repo = InMemoryImportRepository()
_progress_repo = InMemoryProgressRepository()
_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        logger.warning("DATABASE_URL is not set: using in-memory storage. Data is lost on restart.")
        _warned = True


def get_business_repo(db: Optional[Session] = Depends(get_db_optional)):
    if db is None:
        _warn_once()
        return _business_repo
    return SqlBusinessRepository(db)


def get_analysis_repo(db: Optional[Session] = Depends(get_db_optional)):
    if db is None:
        _warn_once()
        return _analysis_repo
    return SqlAnalysisRepository(db)


def get_import_repo(db: Optional[Session] = Depends(get_db_optional)):
    if db is None:
        _warn_once()
        return _import_repo
    return SqlImportRepository(db)


def get_progress_repo(db: Optional[Session] = Depends(get_db_optional)):
    if db is None:
        _warn_once()
        return _progress_repo
    return SqlProgressRepository(db)
