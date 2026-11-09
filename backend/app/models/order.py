"""
SQLAlchemy ORM models for Order Placement and Management:
- Order (placed order with financial and case summaries, lifecycle statuses)
- OrderLine (immutable snapshots of products, pricing, schemes, and fulfilment quantities)
- OrderAuditLog (immutable audit trail of all lifecycle events and corrections)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Text,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    JSON,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from app.core.database import Base


class Order(Base):
    """
    Wholesale order placed by a retailer.
    Lifecycle: SUBMITTED -> APPROVED or SUBMITTED -> REJECTED.
    """
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED', 'APPROVED', 'REJECTED')",
            name="chk_order_status_valid",
        ),
        Index("ix_orders_retailer_status", "retailer_id", "status"),
        Index("ix_orders_created_at_desc", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_desk_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_source: Mapped[str] = mapped_column(
        String(20), default="manual", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="SUBMITTED", index=True, nullable=False
    )

    # Financial totals
    gross_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    scheme_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    net_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    # Case volume totals
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_free_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_fulfilment_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Remarks and review feedback
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Idempotency key for duplicate submission prevention
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )

    # Timestamps
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
    retailer: Mapped["app.models.auth.Retailer"] = relationship("Retailer")
    reviewer: Mapped["app.models.auth.OrderDeskUser | None"] = relationship("OrderDeskUser")
    lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderLine.created_at.asc()",
    )
    audit_logs: Mapped[list["OrderAuditLog"]] = relationship(
        "OrderAuditLog",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderAuditLog.created_at.asc()",
    )


class OrderLine(Base):
    """
    Order line item with frozen pricing and scheme snapshots.
    Preserves exact price and scheme rules from the moment of order placement.
    """
    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("qty_cases > 0", name="chk_order_line_qty_cases_positive"),
        CheckConstraint("free_cases >= 0", name="chk_order_line_free_cases_nonneg"),
        CheckConstraint(
            "fulfilment_qty_cases >= qty_cases",
            name="chk_order_line_fulfilment_ge_cases",
        ),
        Index("ix_order_lines_order_product", "order_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Product snapshots
    sku_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    pack_size_snapshot: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    case_qty_snapshot: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price_per_pack_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    price_per_case_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    # Scheme snapshots (frozen rules at time of order creation)
    scheme_type_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    min_qty_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    free_qty_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    description_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quantities
    qty_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    free_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fulfilment_qty_cases: Mapped[int] = mapped_column(Integer, nullable=False)

    # Financials
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # Price per case
    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    # Optional origin fragment
    raw_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
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
    order: Mapped["Order"] = relationship("Order", back_populates="lines")
    product: Mapped["app.models.catalogue.Product"] = relationship("Product")


class OrderAuditLog(Base):
    """
    Immutable audit trail for order lifecycle transitions and desk corrections.
    """
    __tablename__ = "order_audit_logs"
    __table_args__ = (
        Index("ix_order_audit_logs_order_created", "order_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'retailer' or 'order_desk'
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'SUBMITTED', 'LINE_CORRECTED', 'APPROVED', 'REJECTED'
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="audit_logs")
