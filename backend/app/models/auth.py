"""
SQLAlchemy ORM models for Authentication and Authorization:
- Retailer
- OrderDeskUser
- OTPRecord
- RefreshTokenBlocklist
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    DateTime,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base


class Retailer(Base):
    """
    Kirana shop / retailer account.
    Authenticates via mobile number and OTP.
    """
    __tablename__ = "retailers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mobile: Mapped[str] = mapped_column(
        String(15), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tally_ledger_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    credit_limit: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.0, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


class OrderDeskUser(Base):
    """
    Order Desk staff member.
    Authenticates via email and password.
    """
    __tablename__ = "order_desk_users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


class OTPRecord(Base):
    """
    Tracks OTP lifecycle for retailer mobile login.
    An OTP locks after 5 failed verification attempts.
    """
    __tablename__ = "otp_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mobile: Mapped[str] = mapped_column(String(15), index=True, nullable=False)
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_otp_records_mobile_expires_at", "mobile", "expires_at"),
    )


class RefreshTokenBlocklist(Base):
    """
    Blocklisted/revoked JWT refresh tokens (by JTI).
    """
    __tablename__ = "refresh_token_blocklist"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    jti: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

