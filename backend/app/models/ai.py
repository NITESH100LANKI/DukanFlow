"""
SQLAlchemy ORM models for AI Order Capture & Extraction:
- RetailerAlias (retailer-specific informal term to SKU mapping, learned from confirmations and Desk corrections)
- AIOrderDraft (persistent order drafts parsed from unstructured messages)
- AIOrderDraftLine (extracted items, match statuses, confidence levels, alternatives, and resolved selections)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from app.core.database import Base


class RetailerAlias(Base):
    """
    Retailer-specific product alias mapping.
    Maps an informal term (e.g. 'chhota parle-g', 'surf packet') to a canonical product.
    Strictly isolated per retailer: aliases are NEVER shared between retailers.
    """
    __tablename__ = "retailer_aliases"
    __table_args__ = (
        UniqueConstraint("retailer_id", "raw_term", name="uq_retailer_alias_raw_term"),
        Index("ix_retailer_aliases_lookup", "retailer_id", "raw_term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    raw_term: Mapped[str] = mapped_column(
        String(300), nullable=False
    )  # Lowercase, trimmed, normalized phrase
    source: Mapped[str] = mapped_column(
        String(20), default="retailer", nullable=False
    )  # 'retailer' | 'desk'

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
    product: Mapped["app.models.catalogue.Product"] = relationship("Product")


class AIOrderDraft(Base):
    """
    Persistent AI-extracted order draft.
    Allows retailers to review, resolve ambiguities, and confirm into their shopping cart.
    Drafts NEVER directly place orders or deduct inventory.
    """
    __tablename__ = "ai_order_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'DISCARDED')",
            name="chk_ai_order_draft_status_valid",
        ),
        Index("ix_ai_order_drafts_retailer_status", "retailer_id", "status"),
        Index("ix_ai_order_drafts_created_at_desc", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", index=True, nullable=False
    )  # DRAFT, CONFIRMED, DISCARDED
    parser_used: Mapped[str] = mapped_column(
        String(30), default="gemini", server_default="gemini", nullable=False
    )  # gemini, fallback

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

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
    lines: Mapped[List["AIOrderDraftLine"]] = relationship(
        "AIOrderDraftLine",
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="AIOrderDraftLine.created_at.asc()",
    )


class AIOrderDraftLine(Base):
    """
    Single line item in an AI order draft.
    Tracks extraction fragments, match statuses, confidence levels, alternatives, and user resolutions.
    """
    __tablename__ = "ai_order_draft_lines"
    __table_args__ = (
        CheckConstraint(
            "match_status IN ('confirmed', 'ambiguous', 'unmatched')",
            name="chk_draft_line_match_status_valid",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence IN ('high', 'medium', 'low')",
            name="chk_draft_line_confidence_valid",
        ),
        CheckConstraint(
            "normalized_unit IN ('case', 'piece', 'unknown')",
            name="chk_draft_line_unit_valid",
        ),
        Index("ix_draft_lines_draft_id", "draft_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_order_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Extraction values
    raw_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    product_mention: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_text: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    normalized_unit: Mapped[str] = mapped_column(
        String(20), default="unknown", nullable=False
    )

    # Matching output
    matched_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_status: Mapped[str] = mapped_column(
        String(30), default="unmatched", nullable=False
    )  # confirmed, ambiguous, unmatched
    confidence: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # high, medium, low, None
    clarification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alternatives: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    warning: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Resolution fields
    resolved_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_qty_cases: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    draft: Mapped["AIOrderDraft"] = relationship("AIOrderDraft", back_populates="lines")
    matched_product: Mapped[Optional["app.models.catalogue.Product"]] = relationship(
        "Product", foreign_keys=[matched_product_id]
    )
    resolved_product: Mapped[Optional["app.models.catalogue.Product"]] = relationship(
        "Product", foreign_keys=[resolved_product_id]
    )

