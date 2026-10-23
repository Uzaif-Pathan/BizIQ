from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Text, Numeric, Date, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationProgress(Base):
    __tablename__ = "recommendation_progress"
    __table_args__ = (
        CheckConstraint("status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'ON_HOLD')", name="recommendation_progress_status_check"),
    )

    progress_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress_note: Mapped[str | None] = mapped_column(Text)
    measured_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    due_date: Mapped[date | None] = mapped_column(Date)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_users.user_id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
