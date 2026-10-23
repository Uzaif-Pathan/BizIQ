from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ValidationIssue(Base):
    __tablename__ = "validation_issues"

    __table_args__ = (
        CheckConstraint(
            "resolution_status IN ('OPEN', 'RESOLVED', 'IGNORED')",
            name="validation_issues_resolution_status_check",
        ),
        CheckConstraint(
            "row_number > 0",
            name="validation_issues_row_number_check",
        ),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR')",
            name="validation_issues_severity_check",
        ),
    )

    issue_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("data_imports.import_id", ondelete="CASCADE"),
        nullable=False,
    )

    row_number: Mapped[int | None] = mapped_column(Integer)

    column_name: Mapped[str | None] = mapped_column(String(150))

    issue_type: Mapped[str] = mapped_column(
        String(60), nullable=False
    )

    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    issue_message: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    resolution_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'OPEN'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
