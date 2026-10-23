from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"
    __table_args__ = (
        CheckConstraint("evidence_level IN ('HIGH', 'MEDIUM', 'LOW')", name="analysis_findings_evidence_level_check"),
    )

    finding_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("analysis_runs.analysis_id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    comparison_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    metric_unit: Mapped[str | None] = mapped_column(String(40))
    direction: Mapped[str | None] = mapped_column(String(30))
    evidence_level: Mapped[str] = mapped_column(String(10), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
