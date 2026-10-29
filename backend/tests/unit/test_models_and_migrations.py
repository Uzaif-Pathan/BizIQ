"""Model and migration checks that need no database."""
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402

BACKEND = Path(__file__).resolve().parents[2]


def test_single_migration_head_is_0003():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0003_benchmark_columns"]


def test_unknown_values_can_be_null():
    t = Base.metadata.tables["monthly_financials"]
    for col in ("revenue", "fixed_expenses", "variable_expenses", "other_expenses", "expenses_complete"):
        assert t.c[col].nullable, col
        assert t.c[col].server_default is None, col


def test_new_columns_and_table_exist():
    tables = Base.metadata.tables
    assert {"stage", "description"} <= set(tables["businesses"].c.keys())
    assert {"result_json", "benchmark_status", "error_message"} <= set(tables["analysis_runs"].c.keys())
    assert "external_id" in tables["recommendations"].c
    assert "public_id" in tables["analysis_runs"].c and tables["analysis_runs"].c.public_id.unique
    assert "total_cost" in tables["monthly_product_metrics"].c
    assert "data_type" in tables["data_imports"].c
    ca = tables["customer_activity"]
    assert {"business_id", "customer_ref", "period_start", "transactions", "amount_spent"} <= set(ca.c.keys())
    assert not {"name", "email", "phone"} & set(ca.c.keys())  # customers stay anonymous
