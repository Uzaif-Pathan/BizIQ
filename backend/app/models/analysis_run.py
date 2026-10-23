from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("availability_mode IN ('RICH', 'STANDARD', 'COLD_START')", name="analysis_runs_availability_mode_check"),
        CheckConstraint("evidence_level IN ('HIGH', 'MEDIUM', 'LOW')", name="analysis_runs_evidence_level_check"),
        CheckConstraint("risk_level IN ('LOW', 'MODERATE', 'HIGH', 'UNKNOWN')", name="analysis_runs_risk_level_check"),
        CheckConstraint("run_status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="analysis_runs_run_status_check"),
        CheckConstraint("viability_score >= 0 AND viability_score <= 100", name="analysis_runs_viability_score_check"),
    )

    analysis_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_users.user_id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(10), nullable=False)
    viability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    score_version: Mapped[str | None] = mapped_column(String(30))
    run_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'RUNNING'"))
    limitations: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
