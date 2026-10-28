from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, String, Text, Numeric, Integer, Date, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndustryBenchmark(Base):
    __tablename__ = "industry_benchmarks"
    __table_args__ = (
        CheckConstraint("geography_level IN ('DISTRICT', 'STATE', 'REGION', 'NATIONAL')", name="industry_benchmarks_geography_level_check"),
    )

    benchmark_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("benchmark_sources.source_id"), nullable=False)
    industry_code: Mapped[str | None] = mapped_column(String(30))
    industry_name: Mapped[str | None] = mapped_column(String(150))
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(40))
    geography_level: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'India'"))
    state: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    business_size_band: Mapped[str | None] = mapped_column(String(30))
    reference_year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[date | None] = mapped_column(Date)
    confidence_note: Mapped[str | None] = mapped_column(Text)
