from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, JSON, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("availability_mode IN ('RICH', 'STANDARD', 'COLD_START')", name="analysis_runs_availability_mode_check"),
        CheckConstraint("evidence_level IN ('HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT')", name="analysis_runs_evidence_level_check"),
        CheckConstraint("risk_level IN ('LOW', 'MODERATE', 'HIGH', 'UNKNOWN')", name="analysis_runs_risk_level_check"),
        CheckConstraint("run_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name="analysis_runs_run_status_check"),
        CheckConstraint("viability_score >= 0 AND viability_score <= 100", name="analysis_runs_viability_score_check"),
    )

    analysis_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # The id the API shows (a UUID string); analysis_id stays the integer primary key.
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_users.user_id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    viability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    score_version: Mapped[str | None] = mapped_column(String(30))
    run_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'RUNNING'"))
    limitations: Mapped[str | None] = mapped_column(Text)
    benchmark_status: Mapped[str | None] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    # The full analysis result exactly as the API returns it. This is the source of truth for
    # GET /analyses/{id}; the findings/recommendations tables are a queryable copy.
    result_json: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
