from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("current_status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'ON_HOLD')", name="recommendations_current_status_check"),
        CheckConstraint("evidence_strength IN ('HIGH', 'MEDIUM', 'LOW')", name="recommendations_evidence_strength_check"),
        CheckConstraint("priority IN ('HIGH', 'MEDIUM', 'LOW')", name="recommendations_priority_check"),
    )

    recommendation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("analysis_runs.analysis_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    impact_level: Mapped[str | None] = mapped_column(String(20))
    effort_level: Mapped[str | None] = mapped_column(String(20))
    evidence_strength: Mapped[str] = mapped_column(String(10), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    kpi_name: Mapped[str | None] = mapped_column(String(120))
    kpi_baseline: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    kpi_target: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    current_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'NOT_STARTED'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
