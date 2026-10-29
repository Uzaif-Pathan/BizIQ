from datetime import date

import pytest
from pydantic import ValidationError

from app.repositories.progress import InMemoryProgressRepository
from app.schemas.progress import ProgressStatus, ProgressUpdate


def test_update_accepts_minimal_and_full_payload():
    assert ProgressUpdate(status="in_progress").measured_value is None
    full = ProgressUpdate(status="completed", note="  done  ", measured_value=12.5, due_date="2026-12-01")
    assert full.note == "done" and full.due_date == date(2026, 12, 1)


@pytest.mark.parametrize("bad", [
    {"status": "finished"},
    {"status": "completed", "measured_value": float("nan")},
    {"status": "completed", "measured_value": float("inf")},
    {"status": "completed", "measured_value": 1e16},
    {"status": "completed", "note": "x" * 1001},
    {"status": "completed", "due_date": "tomorrow"},
])
def test_update_rejects_bad_values(bad):
    with pytest.raises(ValidationError):
        ProgressUpdate(**bad)


def test_memory_repo_keeps_history_and_latest():
    repo = InMemoryProgressRepository()
    repo.record("a1", "r1", ProgressUpdate(status="in_progress"))
    repo.record("a1", "r2", ProgressUpdate(status="on_hold", note="waiting"))
    repo.record("a1", "r1", ProgressUpdate(status="completed", measured_value=0))
    repo.record("a2", "r1", ProgressUpdate(status="not_started"))
    assert [p.status for p in repo.history("a1", "r1")] == [ProgressStatus.COMPLETED, ProgressStatus.IN_PROGRESS]
    latest = repo.latest("a1")
    assert {(p.recommendation_id, p.status) for p in latest} == {
        ("r1", ProgressStatus.COMPLETED), ("r2", ProgressStatus.ON_HOLD)}
    assert repo.history("a1", "r1")[0].measured_value == 0  # a real measured 0 is kept
    assert repo.latest("nope") == [] and repo.history("a1", "nope") == []
