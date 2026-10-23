from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonthlyCustomerMetric(Base):
    __tablename__ = "monthly_customer_metrics"
    __table_args__ = (
        UniqueConstraint("business_id", "period_start", name="monthly_customer_metrics_business_id_period_start_key"),
        CheckConstraint("lost_customers >= 0", name="monthly_customer_metrics_lost_customers_check"),
        CheckConstraint("marketing_spend >= 0", name="monthly_customer_metrics_marketing_spend_check"),
        CheckConstraint("new_customers >= 0", name="monthly_customer_metrics_new_customers_check"),
        CheckConstraint("retention_rate >= 0 AND retention_rate <= 100", name="monthly_customer_metrics_retention_rate_check"),
        CheckConstraint("returning_customers >= 0", name="monthly_customer_metrics_returning_customers_check"),
        CheckConstraint("total_customers >= 0", name="monthly_customer_metrics_total_customers_check"),
    )

    customer_metric_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    total_customers: Mapped[int | None] = mapped_column(Integer)
    new_customers: Mapped[int | None] = mapped_column(Integer)
    returning_customers: Mapped[int | None] = mapped_column(Integer)
    lost_customers: Mapped[int | None] = mapped_column(Integer)
    marketing_spend: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    retention_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    source_import_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("data_imports.import_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
