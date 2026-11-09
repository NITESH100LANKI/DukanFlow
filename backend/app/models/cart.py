"""
SQLAlchemy ORM models for Shopping Cart:
- Cart (1-to-1 with Retailer)
- CartLine (line items per cart with unique product constraint)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from app.core.database import Base


class Cart(Base):
    """
    Active shopping cart for a retailer.
    Enforces exactly one persistent active cart per retailer.
    """
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
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
    lines: Mapped[list["CartLine"]] = relationship(
        "CartLine",
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartLine.created_at.asc()",
    )


class CartLine(Base):
    """
    An individual line item within a cart.
    A product can appear at most once per cart.
    Quantity is in wholesale cases (> 0).
    """
    __tablename__ = "cart_lines"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_line_product"),
        CheckConstraint("qty_cases > 0", name="chk_cart_line_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    qty_cases: Mapped[int] = mapped_column(Integer, nullable=False)
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
    cart: Mapped["Cart"] = relationship("Cart", back_populates="lines")
    product: Mapped["app.models.catalogue.Product"] = relationship("Product")
