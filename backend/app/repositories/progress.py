"""Storage for recommendation progress. Every update is kept as history; the newest one is the current status.

A recommendation is identified by (analysis id, the recommendation id shown in the analysis result).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.schemas.progress import ProgressRead, ProgressStatus, ProgressUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryProgressRepository:
    def __init__(self) -> None:
        self._items: Dict[Tuple[str, str], List[ProgressRead]] = {}
        self._next_id = 1

    def record(self, analysis_id: str, recommendation_id: str, data: ProgressUpdate) -> ProgressRead:
        item = ProgressRead(
            id=self._next_id, recommendation_id=recommendation_id, status=data.status, note=data.note,
            measured_value=data.measured_value, due_date=data.due_date, updated_at=_now(),
        )
        self._next_id += 1
        self._items.setdefault((analysis_id, recommendation_id), []).append(item)
        return item

    def history(self, analysis_id: str, recommendation_id: str) -> List[ProgressRead]:
        return list(reversed(self._items.get((analysis_id, recommendation_id), [])))

    def latest(self, analysis_id: str) -> List[ProgressRead]:
        out = [items[-1] for (aid, _), items in self._items.items() if aid == analysis_id and items]
        return sorted(out, key=lambda p: p.id)


class SqlProgressRepository:
    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def _read(row, external_id: str) -> ProgressRead:
        return ProgressRead(
            id=row.progress_id, recommendation_id=external_id, status=ProgressStatus(row.status.lower()),
            note=row.progress_note, measured_value=None if row.measured_value is None else float(row.measured_value),
            due_date=row.due_date, updated_at=row.updated_at,
        )

    def _recommendation(self, analysis_id: str, recommendation_id: str):
        from sqlalchemy import select

        from app.models import AnalysisRun, Recommendation

        return self.db.scalar(
            select(Recommendation).join(AnalysisRun, AnalysisRun.analysis_id == Recommendation.analysis_id)
            .where(AnalysisRun.public_id == analysis_id, Recommendation.external_id == recommendation_id))

    def record(self, analysis_id: str, recommendation_id: str, data: ProgressUpdate) -> Optional[ProgressRead]:
        from app.models import RecommendationProgress

        rec = self._recommendation(analysis_id, recommendation_id)
        if rec is None:
            return None
        try:
            row = RecommendationProgress(
                recommendation_id=rec.recommendation_id, status=data.status.value.upper(),
                progress_note=data.note,
                measured_value=None if data.measured_value is None else Decimal(str(data.measured_value)),
                due_date=data.due_date, updated_at=_now(),
            )
            self.db.add(row)
            rec.current_status = data.status.value.upper()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._read(row, recommendation_id)

    def history(self, analysis_id: str, recommendation_id: str) -> List[ProgressRead]:
        from sqlalchemy import select

        from app.models import RecommendationProgress

        rec = self._recommendation(analysis_id, recommendation_id)
        if rec is None:
            return []
        rows = self.db.scalars(select(RecommendationProgress)
                               .where(RecommendationProgress.recommendation_id == rec.recommendation_id)
                               .order_by(RecommendationProgress.progress_id.desc()))
        return [self._read(r, recommendation_id) for r in rows]

    def latest(self, analysis_id: str) -> List[ProgressRead]:
        from sqlalchemy import select

        from app.models import AnalysisRun, Recommendation, RecommendationProgress

        stmt = (
            select(RecommendationProgress, Recommendation.external_id)
            .join(Recommendation, Recommendation.recommendation_id == RecommendationProgress.recommendation_id)
            .join(AnalysisRun, AnalysisRun.analysis_id == Recommendation.analysis_id)
            .where(AnalysisRun.public_id == analysis_id)
            .order_by(RecommendationProgress.progress_id.desc())
        )
        seen, out = set(), []
        for row, external_id in self.db.execute(stmt):
            if row.recommendation_id not in seen:
                seen.add(row.recommendation_id)
                out.append(self._read(row, external_id))
        return sorted(out, key=lambda p: p.id)
