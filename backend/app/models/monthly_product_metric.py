from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonthlyProductMetric(Base):
    __tablename__ = "monthly_product_metrics"
    __table_args__ = (
        UniqueConstraint("product_id", "period_start", name="monthly_product_metrics_product_id_period_start_key"),
        CheckConstraint("closing_inventory >= 0", name="monthly_product_metrics_closing_inventory_check"),
        CheckConstraint("total_revenue >= 0", name="monthly_product_metrics_total_revenue_check"),
        CheckConstraint("units_returned >= 0", name="monthly_product_metrics_units_returned_check"),
        CheckConstraint("units_sold >= 0", name="monthly_product_metrics_units_sold_check"),
    )

    product_metric_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products_services.product_id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    units_sold: Mapped[int | None] = mapped_column(Integer)
    total_revenue: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    units_returned: Mapped[int | None] = mapped_column(Integer)
    closing_inventory: Mapped[int | None] = mapped_column(Integer)
    source_import_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("data_imports.import_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
