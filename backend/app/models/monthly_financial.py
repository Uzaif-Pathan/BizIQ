from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonthlyFinancial(Base):
    __tablename__ = "monthly_financials"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "period_start",
            name="monthly_financials_business_id_period_start_key",
        ),
        CheckConstraint(
            "revenue >= 0",
            name="monthly_financials_revenue_check",
        ),
        CheckConstraint(
            "fixed_expenses >= 0",
            name="monthly_financials_fixed_expenses_check",
        ),
        CheckConstraint(
            "variable_expenses >= 0",
            name="monthly_financials_variable_expenses_check",
        ),
        CheckConstraint(
            "other_expenses >= 0",
            name="monthly_financials_other_expenses_check",
        ),
        CheckConstraint(
            "investment_amount >= 0",
            name="monthly_financials_investment_amount_check",
        ),
        CheckConstraint(
            "capital_employed >= 0",
            name="monthly_financials_capital_employed_check",
        ),
    )

    financial_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="CASCADE"),
        nullable=False,
    )

    period_start: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    revenue: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
        server_default=text("0"),
    )

    fixed_expenses: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
        server_default=text("0"),
    )

    variable_expenses: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
        server_default=text("0"),
    )

    other_expenses: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
        server_default=text("0"),
    )

    investment_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 2)
    )

    capital_employed: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 2)
    )

    source_import_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("data_imports.import_id", ondelete="SET NULL"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
