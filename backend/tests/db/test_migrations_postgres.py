"""Runs only when TEST_DATABASE_URL points at an EMPTY PostgreSQL database, for example:

    export TEST_DATABASE_URL=postgresql+psycopg://biziq_user:password@localhost:5432/biziq_test

It upgrades the empty database to the latest migration and checks that the result matches the models.
"""
import os
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is not set")
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture()
def migrated(monkeypatch):
    engine = create_engine(URL)
    if set(inspect(engine).get_table_names()) - {"alembic_version"}:
        pytest.fail("TEST_DATABASE_URL must point at an empty database")
    monkeypatch.setenv("DATABASE_URL", URL)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    yield engine, cfg
    command.downgrade(cfg, "base")
    get_settings.cache_clear()


def test_upgrade_matches_models(migrated):
    engine, _ = migrated
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_to_0001_and_back(migrated):
    _, cfg = migrated
    command.downgrade(cfg, "0002_engine_integration")
    command.downgrade(cfg, "48681f5892d3")
    command.upgrade(cfg, "head")
