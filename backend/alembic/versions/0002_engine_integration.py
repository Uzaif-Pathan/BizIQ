"""engine integration: business stage/description, unknown expenses, stored results, customer activity

Revision ID: 0002_engine_integration
Revises: 48681f5892d3
Create Date: 2026-10-29

What this adds (see docs/DATABASE_SCHEMA.md):
* businesses: stage, description
* monthly_financials: expenses_complete; revenue and the three expense columns may now be NULL
  (unknown is stored as NULL, never as 0)
* analysis_runs: public_id (the id the API shows), result_json, benchmark_status, error_message; evidence_level also allows INSUFFICIENT;
  run_status also allows PENDING
* monthly_product_metrics: total_cost
* recommendations: external_id (the engine's id, e.g. REC-LOSS)
* data_imports: data_type
* customer_activity: one row per customer per month
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_engine_integration"
down_revision: Union[str, Sequence[str], None] = "48681f5892d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # businesses -------------------------------------------------------------------------------
    op.add_column("businesses", sa.Column("stage", sa.String(length=20), server_default=sa.text("'established'"), nullable=False))
    op.add_column("businesses", sa.Column("description", sa.Text(), nullable=True))
    op.create_check_constraint("businesses_stage_check", "businesses", "stage IN ('new', 'established')")

    # monthly_financials: unknown must be storable ----------------------------------------------
    op.add_column("monthly_financials", sa.Column("expenses_complete", sa.Boolean(), nullable=True))
    for col in ("revenue", "fixed_expenses", "variable_expenses", "other_expenses"):
        op.alter_column("monthly_financials", col, existing_type=sa.Numeric(16, 2),
                        nullable=True, server_default=None)

    # analysis_runs ------------------------------------------------------------------------------
    op.add_column("analysis_runs", sa.Column("public_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE analysis_runs SET public_id = 'legacy-' || analysis_id::text WHERE public_id IS NULL")
    op.alter_column("analysis_runs", "public_id", existing_type=sa.String(length=64), nullable=False)
    op.create_unique_constraint("analysis_runs_public_id_key", "analysis_runs", ["public_id"])
    op.add_column("monthly_product_metrics", sa.Column("total_cost", sa.Numeric(16, 2), nullable=True))
    op.create_check_constraint("monthly_product_metrics_total_cost_check", "monthly_product_metrics", "total_cost >= 0")
    op.add_column("analysis_runs", sa.Column("benchmark_status", sa.String(length=20), nullable=True))
    op.add_column("analysis_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("analysis_runs", sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column("analysis_runs", "evidence_level", existing_type=sa.String(length=10),
                    type_=sa.String(length=20), existing_nullable=False)
    op.drop_constraint("analysis_runs_evidence_level_check", "analysis_runs", type_="check")
    op.create_check_constraint("analysis_runs_evidence_level_check", "analysis_runs",
                               "evidence_level IN ('HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT')")
    op.drop_constraint("analysis_runs_run_status_check", "analysis_runs", type_="check")
    op.create_check_constraint("analysis_runs_run_status_check", "analysis_runs",
                               "run_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")

    # recommendations ------------------------------------------------------------------------------
    op.add_column("recommendations", sa.Column("external_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint("recommendations_analysis_id_external_id_key", "recommendations",
                                ["analysis_id", "external_id"])

    # data_imports -----------------------------------------------------------------------------------
    op.add_column("data_imports", sa.Column("data_type", sa.String(length=20), server_default=sa.text("'FINANCIALS'"), nullable=False))
    op.create_check_constraint("data_imports_data_type_check", "data_imports",
                               "data_type IN ('FINANCIALS', 'CUSTOMERS', 'PRODUCTS')")

    # customer_activity -------------------------------------------------------------------------------
    op.create_table(
        "customer_activity",
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("business_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_ref", sa.String(length=100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("transactions", sa.Integer(), nullable=True),
        sa.Column("amount_spent", sa.Numeric(16, 2), nullable=True),
        sa.Column("source_import_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("transactions >= 0", name="customer_activity_transactions_check"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.business_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_import_id"], ["data_imports.import_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("activity_id"),
        sa.UniqueConstraint("business_id", "customer_ref", "period_start",
                            name="customer_activity_business_id_customer_ref_period_start_key"),
    )
    op.create_index("ix_customer_activity_business_period", "customer_activity", ["business_id", "period_start"])


def downgrade() -> None:
    op.drop_index("ix_customer_activity_business_period", table_name="customer_activity")
    op.drop_table("customer_activity")

    op.drop_constraint("data_imports_data_type_check", "data_imports", type_="check")
    op.drop_column("data_imports", "data_type")

    op.drop_constraint("recommendations_analysis_id_external_id_key", "recommendations", type_="unique")
    op.drop_column("recommendations", "external_id")

    # Rows that use the new values cannot be kept when the old rules are restored.
    op.execute("UPDATE analysis_runs SET evidence_level = 'LOW' WHERE evidence_level = 'INSUFFICIENT'")
    op.execute("UPDATE analysis_runs SET run_status = 'RUNNING' WHERE run_status = 'PENDING'")
    op.drop_constraint("analysis_runs_run_status_check", "analysis_runs", type_="check")
    op.create_check_constraint("analysis_runs_run_status_check", "analysis_runs",
                               "run_status IN ('RUNNING', 'COMPLETED', 'FAILED')")
    op.drop_constraint("analysis_runs_evidence_level_check", "analysis_runs", type_="check")
    op.create_check_constraint("analysis_runs_evidence_level_check", "analysis_runs",
                               "evidence_level IN ('HIGH', 'MEDIUM', 'LOW')")
    op.alter_column("analysis_runs", "evidence_level", existing_type=sa.String(length=20),
                    type_=sa.String(length=10), existing_nullable=False)
    op.drop_column("analysis_runs", "result_json")
    op.drop_column("analysis_runs", "error_message")
    op.drop_column("analysis_runs", "benchmark_status")
    op.drop_constraint("monthly_product_metrics_total_cost_check", "monthly_product_metrics", type_="check")
    op.drop_column("monthly_product_metrics", "total_cost")
    op.drop_constraint("analysis_runs_public_id_key", "analysis_runs", type_="unique")
    op.drop_column("analysis_runs", "public_id")

    # NULLs cannot go back into NOT NULL columns; they become 0 only on downgrade, which is documented.
    for col in ("revenue", "fixed_expenses", "variable_expenses", "other_expenses"):
        op.execute(f"UPDATE monthly_financials SET {col} = 0 WHERE {col} IS NULL")
        op.alter_column("monthly_financials", col, existing_type=sa.Numeric(16, 2),
                        nullable=False, server_default=sa.text("0"))
    op.drop_column("monthly_financials", "expenses_complete")

    op.drop_constraint("businesses_stage_check", "businesses", type_="check")
    op.drop_column("businesses", "description")
    op.drop_column("businesses", "stage")
