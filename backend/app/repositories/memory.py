"""Temporary in-memory storage.

These classes have the same methods a SQLAlchemy repository will need.
When the database models are ready, write DB versions with the same method
names and change the two functions in app/api/deps.py. The routes stay as they are.

Data is lost when the server restarts. That is expected for this stage.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.analysis import AnalysisResult, AnalysisRunSummary, AnalysisStatus
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryBusinessRepository:
    def __init__(self) -> None:
        self._items: Dict[int, BusinessRead] = {}
        self._next_id = 1

    def create(self, data: BusinessCreate) -> BusinessRead:
        now = _now()
        business = BusinessRead(
            **data.model_dump(), id=self._next_id, created_at=now, updated_at=now
        )
        self._next_id += 1
        self._items[business.id] = business
        return business

    def list(self, limit: int = 50, offset: int = 0) -> List[BusinessRead]:
        items = sorted(self._items.values(), key=lambda b: b.created_at, reverse=True)
        return items[offset : offset + limit]

    def get(self, business_id: int) -> Optional[BusinessRead]:
        return self._items.get(business_id)

    def delete(self, business_id: int) -> bool:
        """Remove a business; return False when it does not exist."""
        return self._items.pop(business_id, None) is not None

    def update(self, business_id: int, data: BusinessUpdate) -> Optional[BusinessRead]:
        current = self._items.get(business_id)
        if current is None:
            return None
        changes = data.model_dump(exclude_unset=True)
        updated = current.model_copy(update={**changes, "updated_at": _now()})
        self._items[business_id] = updated
        return updated

    def set_latest_analysis_status(
        self, business_id: int, status: AnalysisStatus
    ) -> None:
        current = self._items.get(business_id)
        if current is not None:
            self._items[business_id] = current.model_copy(
                update={"latest_analysis_status": status}
            )


class InMemoryAnalysisRepository:
    def __init__(self) -> None:
        self._items: Dict[str, AnalysisResult] = {}

    def save(self, result: AnalysisResult) -> AnalysisResult:
        self._items[result.analysis_id] = result
        return result

    def get(self, analysis_id: str) -> Optional[AnalysisResult]:
        return self._items.get(analysis_id)

    def delete_for_business(self, business_id: int) -> None:
        """Delete in-memory analysis records owned by a business."""
        for analysis_id, result in list(self._items.items()):
            try:
                matches = int(result.business_id) == business_id
            except (TypeError, ValueError):
                matches = False
            if matches:
                del self._items[analysis_id]

    def list_for_business(self, business_id: str) -> List[AnalysisRunSummary]:
        runs = [r for r in self._items.values() if r.business_id == business_id]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return [AnalysisRunSummary.model_validate(r, from_attributes=True) for r in runs]
