from datetime import datetime

from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("analysis_runs.analysis_id"), nullable=False)
    report_title: Mapped[str] = mapped_column(String(250), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'en'"))
    file_format: Mapped[str] = mapped_column(String(15), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_users.user_id", ondelete="SET NULL"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
