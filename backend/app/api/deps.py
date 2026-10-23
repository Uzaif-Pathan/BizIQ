"""FastAPI dependencies.

Swap the two repository functions for database versions when the SQLAlchemy
models are ready. Nothing else needs to change.
"""

from app.repositories.memory import (
    InMemoryAnalysisRepository,
    InMemoryBusinessRepository,
)

_business_repo = InMemoryBusinessRepository()
_analysis_repo = InMemoryAnalysisRepository()


def get_business_repo() -> InMemoryBusinessRepository:
    return _business_repo


def get_analysis_repo() -> InMemoryAnalysisRepository:
    return _analysis_repo
