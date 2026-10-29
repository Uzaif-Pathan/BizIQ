"""The seed script creates the synthetic businesses and the engine can analyse them."""
import importlib.util
import os
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import select  # noqa: E402

from app.models import Business  # noqa: E402
from app.repositories.sql import SqlAnalysisRepository, SqlBusinessRepository  # noqa: E402
from app.schemas.analysis import AnalysisStatus  # noqa: E402
from app.services import analysis_service  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "seed_demo_data.py"


def _run_seed(monkeypatch):
    from app.core.config import get_settings
    from app.db import session

    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    for cached in (get_settings, session.get_engine, session.get_sessionmaker):
        cached.cache_clear()
    spec = importlib.util.spec_from_file_location("seed_demo_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main()
    for cached in (get_settings, session.get_engine, session.get_sessionmaker):
        cached.cache_clear()
    return code


def test_seed_is_repeatable_and_analysable(db, monkeypatch):
    assert _run_seed(monkeypatch) == 0
    assert _run_seed(monkeypatch) == 0  # second run skips existing businesses
    db.expire_all()
    names = list(db.scalars(select(Business.business_name).order_by(Business.business_id)))
    assert names == ["Demo General Store", "Demo Tailoring Studio", "Demo New Cafe"]

    from app.services.data_loader import load_engine_data
    from analytics_engine.api_adapter import run_for_service

    brepo, arepo = SqlBusinessRepository(db), SqlAnalysisRepository(db)
    retail = next(b for b in brepo.list() if b.name == "Demo General Store")
    r = analysis_service.run_analysis(
        retail, lambda biz: run_for_service(biz, load_engine_data(db, int(biz.id))), arepo, brepo)
    assert r.status == AnalysisStatus.COMPLETED
    assert r.metrics.profit is not None and r.series and r.health_score
    assert r.metrics.revenue == 3726825.0  # same figure as running the engine on the CSV files


def test_benchmarks_load_and_route_logic(db):
    import importlib.util

    from app.models import IndustryBenchmark
    from app.services.benchmark_service import load_candidate_rows, select_benchmarks

    spec = importlib.util.spec_from_file_location("load_benchmarks", SCRIPT.with_name("load_benchmarks.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.load(db).startswith("loaded")
    assert module.load(db).startswith("already loaded")
    assert module.load(db, reload=True).startswith("loaded")
    total = db.query(IndustryBenchmark).count()
    assert total == 7128 - 330 - 0 or total > 6000
    assert db.query(IndustryBenchmark).filter(IndustryBenchmark.metric_value == 0).count() == 0
    out = select_benchmarks(load_candidate_rows(db),
                            {"industry": "grocery retail", "business_type": "retail", "state": "Maharashtra"})
    assert out["status"] == "available" and out["items"] and all(i["source"] for i in out["items"])
