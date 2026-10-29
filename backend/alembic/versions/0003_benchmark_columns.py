"""benchmark breakdown columns for the ASUSE survey data

Revision ID: 0003_benchmark_columns
Revises: 0002_engine_integration
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_benchmark_columns"
down_revision: Union[str, Sequence[str], None] = "0002_engine_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("industry_benchmarks", sa.Column("sector", sa.String(length=20), nullable=True))
    op.add_column("industry_benchmarks", sa.Column("establishment_type", sa.String(length=10), nullable=True))
    op.add_column("industry_benchmarks", sa.Column("worker_group", sa.String(length=20), nullable=True))
    op.add_column("industry_benchmarks", sa.Column("industry_scheme", sa.String(length=30), nullable=True))
    op.add_column("industry_benchmarks", sa.Column("is_rollup", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_index("ix_industry_benchmarks_lookup", "industry_benchmarks",
                    ["metric_name", "geography_level", "state", "industry_name"])


def downgrade() -> None:
    op.drop_index("ix_industry_benchmarks_lookup", table_name="industry_benchmarks")
    for col in ("is_rollup", "industry_scheme", "worker_group", "establishment_type", "sector"):
        op.drop_column("industry_benchmarks", col)
