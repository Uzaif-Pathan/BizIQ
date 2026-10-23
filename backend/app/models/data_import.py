from datetime import datetime

from sqlalchemy import (
    BigInteger,
    String,
    Integer,
    DateTime,
    ForeignKey,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataImport(Base):
    __tablename__ = "data_imports"

    __table_args__ = (
        CheckConstraint(
            "import_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="data_imports_import_status_check",
        ),
        CheckConstraint(
            "rows_received >= 0",
            name="data_imports_rows_received_check",
        ),
        CheckConstraint(
            "rows_accepted >= 0",
            name="data_imports_rows_accepted_check",
        ),
        CheckConstraint(
            "rows_rejected >= 0",
            name="data_imports_rows_rejected_check",
        ),
    )

    import_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    business_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("businesses.business_id", ondelete="CASCADE"),
        nullable=False,
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("app_users.user_id", ondelete="SET NULL"),
    )

    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    file_format: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'USER_UPLOAD'"),
    )

    import_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'PENDING'"),
    )

    rows_received: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    rows_accepted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    rows_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
