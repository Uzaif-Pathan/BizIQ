from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CustomerActivity(Base):
    """One row per customer per month: what the analytics engine needs for repeat-customer,
    concentration and segmentation results.

    ``customer_ref`` is an anonymous reference chosen by the business (for example C001). Do not store
    names, phone numbers or e-mail addresses here. Unknown values are NULL, never 0.
    """

    __tablename__ = "customer_activity"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "customer_ref", "period_start",
            name="customer_activity_business_id_customer_ref_period_start_key",
        ),
        CheckConstraint("transactions >= 0", name="customer_activity_transactions_check"),
        Index("ix_customer_activity_business_period", "business_id", "period_start"),
    )

    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False
    )
    customer_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    transactions: Mapped[int | None] = mapped_column(Integer)
    amount_spent: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    source_import_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("data_imports.import_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
