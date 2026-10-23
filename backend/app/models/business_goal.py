from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    String,
    Text,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BusinessGoal(Base):
    __tablename__ = "business_goals"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ACHIEVED', 'PAUSED', 'CANCELLED')",
            name="business_goals_status_check",
        ),
    )

    goal_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="CASCADE"),
        nullable=False,
    )

    goal_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    target_value: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 2)
    )

    target_date: Mapped[date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'ACTIVE'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
