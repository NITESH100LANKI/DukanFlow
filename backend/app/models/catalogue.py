"""
SQLAlchemy ORM models for Product Catalogue and Schemes:
- Product
- Scheme
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from app.core.database import Base


class Product(Base):
    """
    Distributor's FMCG product catalogue.
    Pricing note: dealer_price_per_pack is a DEMO ASSUMPTION.
    Price unit is tracked explicitly ('per_pack').
    dealer_price_per_case is derived at runtime: dealer_price_per_pack * case_qty.
    """
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sku: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    case_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    dealer_price_per_pack: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    price_unit: Mapped[str] = mapped_column(
        String(20), default="per_pack", nullable=False
    )
    gst_rate_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    stock_cases: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    category: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    schemes: Mapped[list["Scheme"]] = relationship(
        "Scheme",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="desc(Scheme.created_at)",
    )

    @property
    def dealer_price_per_case(self) -> Decimal:
        """Derived runtime calculation: price per pack × case quantity."""
        return round(self.dealer_price_per_pack * self.case_qty, 2)


class Scheme(Base):
    """
    Promotional schemes attached to products.
    Supported types:
    - BUY_N_GET_M_FREE: Retailer buys min_qty cases, gets free_qty cases free.
    - DISCOUNT_ON_MIN_QTY: Retailer buys min_qty cases, gets discount_pct % off.
    """
    __tablename__ = "schemes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheme_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # BUY_N_GET_M_FREE | DISCOUNT_ON_MIN_QTY
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    free_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product", back_populates="schemes"
    )

    @property
    def description(self) -> str:
        """Human-readable description of scheme."""
        if self.scheme_type == "BUY_N_GET_M_FREE":
            return f"Buy {self.min_qty} cases Get {self.free_qty or 1} Free"
        elif self.scheme_type == "DISCOUNT_ON_MIN_QTY":
            pct = int(self.discount_pct) if self.discount_pct and self.discount_pct % 1 == 0 else self.discount_pct
            return f"{pct}% discount on {self.min_qty} or more cases"
        return "Promotional scheme"
