from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Numeric, Integer, Date, DateTime, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        CheckConstraint("average_rating >= 0 AND average_rating <= 5", name="market_snapshots_average_rating_check"),
        CheckConstraint("minimum_price IS NULL OR maximum_price IS NULL OR minimum_price <= maximum_price", name="market_snapshots_check"),
        CheckConstraint("competitor_count >= 0", name="market_snapshots_competitor_count_check"),
        CheckConstraint("maximum_price >= 0", name="market_snapshots_maximum_price_check"),
        CheckConstraint("minimum_price >= 0", name="market_snapshots_minimum_price_check"),
        CheckConstraint("search_radius_km >= 0", name="market_snapshots_search_radius_km_check"),
        CheckConstraint("total_reviews >= 0", name="market_snapshots_total_reviews_check"),
    )

    market_snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    search_radius_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    competitor_count: Mapped[int | None] = mapped_column(Integer)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    total_reviews: Mapped[int | None] = mapped_column(Integer)
    minimum_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    maximum_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    source_name: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
