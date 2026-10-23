from sqlalchemy import BigInteger, Boolean, String, Text, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "app_users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    password_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'en'")
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
