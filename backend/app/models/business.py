from datetime import date, datetime

from sqlalchemy import BigInteger, String, Integer, Date, DateTime, ForeignKey, text, CHAR, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
    CheckConstraint(
        "employee_count >= 0",
        name="businesses_employee_count_check",
    ),
)

    business_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.user_id"),
        nullable=False
    )

    business_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    business_type: Mapped[str | None] = mapped_column(String(80))
    industry_code: Mapped[str | None] = mapped_column(String(30))
    industry_name: Mapped[str | None] = mapped_column(String(150))
    business_model: Mapped[str | None] = mapped_column(String(100))
    target_segment: Mapped[str | None] = mapped_column(String(150))

    country: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'India'")
    )

    state: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))

    established_on: Mapped[date | None] = mapped_column(Date)
    size_band: Mapped[str | None] = mapped_column(String(30))
    employee_count: Mapped[int | None] = mapped_column(Integer)

    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'INR'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
