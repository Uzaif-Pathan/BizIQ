from datetime import datetime

from sqlalchemy import BigInteger, String, Text, Integer, DateTime, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BenchmarkSource(Base):
    __tablename__ = "benchmark_sources"
    __table_args__ = (
        CheckConstraint("reference_year >= 1900 AND reference_year <= 2200", name="benchmark_sources_reference_year_check"),
    )

    source_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    reference_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
