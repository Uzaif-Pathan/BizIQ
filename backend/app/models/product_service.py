from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, String, Boolean, Numeric, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductService(Base):
    __tablename__ = "products_services"
    __table_args__ = (
        UniqueConstraint("business_id", "sku", name="products_services_business_id_sku_key"),
        CheckConstraint("item_type IN ('PRODUCT', 'SERVICE')", name="products_services_item_type_check"),
        CheckConstraint("unit_cost >= 0", name="products_services_unit_cost_check"),
        CheckConstraint("unit_price >= 0", name="products_services_unit_price_check"),
    )

    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    sku: Mapped[str | None] = mapped_column(String(100))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
