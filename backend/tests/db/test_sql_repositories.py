"""Repository and end-to-end tests against PostgreSQL (see tests/db/conftest.py)."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from app.models import CustomerActivity, MonthlyFinancial, MonthlyProductMetric, ProductService  # noqa: E402
from app.repositories.sql import SqlAnalysisRepository, SqlBusinessRepository  # noqa: E402
from app.schemas.analysis import AnalysisResult, AnalysisStatus  # noqa: E402
from app.schemas.business import BusinessCreate, BusinessUpdate  # noqa: E402
from app.services import analysis_service  # noqa: E402
from app.services.analytics_service import mock_engine  # noqa: E402


def _create(repo, **kw):
    base = dict(name="Sharma Traders", industry="Grocery", business_type="retail", goals=["Grow sales", "Cut waste"])
    return repo.create(BusinessCreate(**{**base, **kw}))


def test_business_round_trip_and_goals(db):
    repo = SqlBusinessRepository(db)
    b = _create(repo, city="Pune", stage="new", description="Corner shop", employee_count=3)
    assert isinstance(b.id, int) and b.goals == ["Grow sales", "Cut waste"]
    got = repo.get(b.id)
    assert got.name == "Sharma Traders" and got.stage.value == "new" and got.city == "Pune"
    assert got.latest_analysis_status is None
    assert repo.get(999999999) is None


def test_update_changes_only_sent_fields_and_replaces_goals(db):
    repo = SqlBusinessRepository(db)
    b = _create(repo)
    u = repo.update(b.id, BusinessUpdate(city="Nashik", goals=["New goal"]))
    assert u.city == "Nashik" and u.goals == ["New goal"] and u.name == "Sharma Traders"
    assert u.updated_at >= b.updated_at
    assert repo.update(999999999, BusinessUpdate(city="X")) is None


def test_list_newest_first_with_paging(db):
    repo = SqlBusinessRepository(db)
    ids = [_create(repo, name=f"Shop {i}").id for i in range(3)]
    assert [b.id for b in repo.list()] == ids[::-1]
    assert len(repo.list(limit=2)) == 2 and len(repo.list(limit=2, offset=2)) == 1


def test_analysis_lifecycle_and_derived_status(db):
    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)
    result = analysis_service.run_analysis(b, mock_engine, arepo, brepo)
    assert result.status == AnalysisStatus.COMPLETED
    saved = arepo.get(result.analysis_id)
    assert saved is not None and saved.analysis_id == result.analysis_id
    assert saved.metrics.revenue == 286800 and saved.recommendations[0].recommendation_id == "r-001"
    assert brepo.get(b.id).latest_analysis_status == AnalysisStatus.COMPLETED
    history = arepo.list_for_business(str(b.id))
    assert [h.analysis_id for h in history] == [result.analysis_id] and history[0].method_version == "mock-test-0.1.0"
    assert arepo.get("does-not-exist") is None and arepo.list_for_business("not-a-number") == []


def test_findings_and_recommendations_are_also_stored_as_rows(db):
    from sqlalchemy import select

    from app.models import AnalysisFinding, Recommendation

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)
    analysis_service.run_analysis(b, mock_engine, arepo, brepo)
    recs = list(db.scalars(select(Recommendation)))
    assert [r.external_id for r in recs] == ["r-001"] and recs[0].priority == "HIGH" and recs[0].current_status == "NOT_STARTED"
    assert len(list(db.scalars(select(AnalysisFinding)))) == 1


def test_failed_run_is_stored_with_reason(db):
    from analytics_engine.api_adapter import EngineRunFailed

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)

    def engine(_b):
        raise EngineRunFailed("no_usable_data", "None of the provided tables could be used.")

    r = analysis_service.run_analysis(b, engine, arepo, brepo)
    saved = arepo.get(r.analysis_id)
    assert saved.status == AnalysisStatus.FAILED and saved.error_code == "no_usable_data"
    assert brepo.get(b.id).latest_analysis_status == AnalysisStatus.FAILED


def test_real_engine_on_stored_rows(db):
    """Store 12 months of data, run the real engine through the loader, expect real results."""
    from app.services.data_loader import load_engine_data
    from analytics_engine.api_adapter import run_for_service

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)
    for m in range(1, 13):
        db.add(MonthlyFinancial(business_id=b.id, period_start=date(2025, m, 1), revenue=Decimal(100000 + m * 1000),
                                other_expenses=Decimal(80000), expenses_complete=True))
        for c in range(1, 8):
            db.add(CustomerActivity(business_id=b.id, customer_ref=f"C{c:03d}", period_start=date(2025, m, 1),
                                    transactions=2, amount_spent=Decimal(1000 * c)))
    prod = ProductService(business_id=b.id, item_name="Rice", item_type="PRODUCT")
    db.add(prod)
    db.flush()
    for m in range(1, 13):
        db.add(MonthlyProductMetric(product_id=prod.product_id, period_start=date(2025, m, 1), units_sold=50,
                                    total_revenue=Decimal(20000), total_cost=Decimal(15000)))
    db.commit()

    tables = load_engine_data(db, b.id)
    assert all(t is not None for t in tables.values())
    r = analysis_service.run_analysis(b, lambda biz: run_for_service(biz, load_engine_data(db, int(biz.id))), arepo, brepo)
    assert r.status == AnalysisStatus.COMPLETED
    assert r.metrics.profit is not None and r.metrics.profit_margin is not None
    assert r.series and r.series["financial_monthly"] and r.health_score


def test_unknown_expenses_give_no_profit(db):
    from app.services.data_loader import load_engine_data
    from analytics_engine.api_adapter import run_for_service

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)
    for m in range(1, 13):
        db.add(MonthlyFinancial(business_id=b.id, period_start=date(2025, m, 1), revenue=Decimal(100000)))
    db.commit()
    r = analysis_service.run_analysis(b, lambda biz: run_for_service(biz, load_engine_data(db, int(biz.id))), arepo, brepo)
    assert r.metrics.revenue == 1200000 and r.metrics.profit is None


def test_recommendation_progress_round_trip(db):
    from app.models import Recommendation
    from app.repositories.progress import SqlProgressRepository
    from app.schemas.progress import ProgressStatus, ProgressUpdate

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    b = _create(brepo)
    r = analysis_service.run_analysis(b, mock_engine, arepo, brepo)  # mock engine: recommendation "r-001"
    repo = SqlProgressRepository(db)
    first = repo.record(r.analysis_id, "r-001", ProgressUpdate(status="in_progress", note="started"))
    second = repo.record(r.analysis_id, "r-001", ProgressUpdate(status="completed", measured_value=18.5,
                                                                due_date="2026-12-31"))
    assert first.status == ProgressStatus.IN_PROGRESS and second.measured_value == 18.5
    assert [p.status for p in repo.history(r.analysis_id, "r-001")] == [ProgressStatus.COMPLETED,
                                                                        ProgressStatus.IN_PROGRESS]
    assert [(p.recommendation_id, p.status) for p in repo.latest(r.analysis_id)] == [
        ("r-001", ProgressStatus.COMPLETED)]
    assert db.scalars(select_recommendation()).one().current_status == "COMPLETED"
    assert repo.record(r.analysis_id, "missing", ProgressUpdate(status="completed")) is None
    assert repo.history(r.analysis_id, "missing") == [] and repo.latest("no-such-analysis") == []


def select_recommendation():
    from sqlalchemy import select

    from app.models import Recommendation

    return select(Recommendation)


def test_delete_business_returns_false_for_missing_and_cascades_analysis_rows(db):
    from sqlalchemy import select

    from app.models import AnalysisFinding, AnalysisRun, Recommendation

    repo, analysis_repo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    business = _create(repo)
    analysis_service.run_analysis(business, mock_engine, analysis_repo, repo)
    assert db.scalar(select(AnalysisRun.analysis_id).limit(1)) is not None

    assert repo.delete(business.id) is True
    assert repo.get(business.id) is None
    assert db.scalar(select(AnalysisRun.analysis_id).limit(1)) is None
    assert db.scalar(select(AnalysisFinding.finding_id).limit(1)) is None
    assert db.scalar(select(Recommendation.recommendation_id).limit(1)) is None
    assert repo.delete(business.id) is False
