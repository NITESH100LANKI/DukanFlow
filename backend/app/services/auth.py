"""
Modular Authentication Service implementing OTP generation & verification,
password authentication, token rotation, and revocation.
"""

import logging
import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_otp,
    verify_otp_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.auth import (
    Retailer,
    OrderDeskUser,
    OTPRecord,
    RefreshTokenBlocklist,
)
from app.schemas.auth import (
    TokenResponse,
    RetailerInfo,
    DeskUserInfo,
)
from app.services.sms_provider import (
    Fast2SMSProvider,
    SMSProviderError,
    SMSProviderConfigurationError,
    SMSTimeoutError,
    SMSDeliveryError,
)

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and token lifecycle management service."""

    @staticmethod
    async def request_otp(
        db: Session,
        mobile: str,
        provider: Optional[Fast2SMSProvider] = None,
    ) -> dict:
        """
        Generates and stores a hashed OTP for retailer mobile login.
        Enforces 10-minute rate limit (max 3 requests per mobile).
        Dispatches OTP via Fast2SMS Smart OTP provider when configured.
        """
        # Verify that retailer exists and is active
        stmt = select(Retailer).where(
            Retailer.mobile == mobile, Retailer.is_active.is_(True)
        )
        retailer = db.execute(stmt).scalar_one_or_none()
        if not retailer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active retailer account found with this mobile number",
            )

        now = datetime.now(timezone.utc)
        ten_minutes_ago = now - timedelta(minutes=10)

        # Rate limit check: max 3 requests per mobile within 10 minutes
        rate_stmt = select(func.count(OTPRecord.id)).where(
            OTPRecord.mobile == mobile,
            OTPRecord.created_at >= ten_minutes_ago,
        )
        recent_requests = db.execute(rate_stmt).scalar() or 0
        if recent_requests >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please wait a few minutes before trying again.",
            )

        # Safety guards for production environments
        if settings.ENVIRONMENT == "production":
            if settings.DEMO_MODE:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Configuration error: DEMO_MODE must be disabled in production.",
                )
            # A boolean flag alone cannot bypass the absence of a real SMS provider.
            if settings.SMS_PROVIDER != "fast2sms":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Production SMS provider is not implemented. Retailer OTP authentication is "
                        "disabled until a real SMS delivery integration exists and is configured."
                    ),
                )
            if not settings.is_sms_configured:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Fast2SMS credentials or OTP template ID are missing. "
                        "Retailer OTP authentication is unavailable."
                    ),
                )

        # Generate OTP (fixed demo OTP or cryptographically secure 6-digit random)
        if settings.DEMO_MODE:
            plain_otp = settings.DEMO_OTP
        else:
            plain_otp = f"{secrets.randbelow(900000) + 100000}"

        # If SMS provider is configured, send the plain OTP via Fast2SMS BEFORE committing
        if settings.SMS_PROVIDER == "fast2sms":
            active_provider = provider or Fast2SMSProvider()
            try:
                await active_provider.send_otp(mobile=mobile, otp=plain_otp)
            except SMSProviderConfigurationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"SMS gateway configuration error: {str(exc)}",
                ) from exc
            except SMSTimeoutError as exc:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="SMS gateway timed out. Please try again shortly.",
                ) from exc
            except SMSDeliveryError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SMS gateway delivery failure: {str(exc)}",
                ) from exc

        hashed_code = hash_otp(plain_otp)
        expires_at = now + timedelta(minutes=10)

        otp_record = OTPRecord(
            mobile=mobile,
            otp_hash=hashed_code,
            attempts=0,
            locked=False,
            verified=False,
            expires_at=expires_at,
        )
        db.add(otp_record)
        db.commit()

        return {"message": "OTP sent", "expires_in_seconds": 600}

    @staticmethod
    def verify_otp(
        db: Session, mobile: str, plain_otp: str
    ) -> Tuple[TokenResponse, str, datetime]:
        """
        Verifies an OTP and issues access + refresh tokens.
        Locks OTP record after 5 failed attempts.
        """
        now = datetime.now(timezone.utc)

        # Retrieve the latest active OTP record for this mobile
        stmt = (
            select(OTPRecord)
            .where(
                OTPRecord.mobile == mobile,
                OTPRecord.verified.is_(False),
                OTPRecord.expires_at > now,
            )
            .order_by(OTPRecord.created_at.desc())
            .limit(1)
        )
        record = db.execute(stmt).scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP. Please request a new one.",
            )

        if record.locked:
            raise HTTPException(
                status_code=423,  # HTTP 423 Locked
                detail="OTP is locked due to 5 failed attempts. Please request a new one.",
            )

        # Verify hash
        is_valid = verify_otp_hash(plain_otp, record.otp_hash)
        if not is_valid:
            record.attempts += 1
            if record.attempts >= 5:
                record.locked = True
                db.commit()
                raise HTTPException(
                    status_code=423,
                    detail="OTP is locked due to 5 failed attempts. Please request a new one.",
                )
            db.commit()
            remaining = 5 - record.attempts
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid OTP. {remaining} attempt(s) remaining.",
            )

        # Mark OTP as verified and locked
        record.verified = True
        record.locked = True

        # Fetch retailer
        ret_stmt = select(Retailer).where(
            Retailer.mobile == mobile, Retailer.is_active.is_(True)
        )
        retailer = db.execute(ret_stmt).scalar_one_or_none()
        if not retailer:
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retailer account not found or disabled",
            )

        # Issue tokens
        access_token, _, expires_in = create_access_token(
            subject=str(retailer.id), role="retailer"
        )
        refresh_token, _, refresh_expires_at = create_refresh_token(
            subject=str(retailer.id), role="retailer"
        )

        db.commit()

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            retailer=RetailerInfo(
                id=str(retailer.id),
                name=retailer.name,
                mobile=retailer.mobile,
                address=retailer.address,
            ),
        )
        return token_response, refresh_token, refresh_expires_at

    @staticmethod
    def desk_login(
        db: Session, email: str, plain_password: str
    ) -> Tuple[TokenResponse, str, datetime]:
        """
        Authenticates an Order Desk user with email and password.
        """
        stmt = select(OrderDeskUser).where(OrderDeskUser.email == email)
        user = db.execute(stmt).scalar_one_or_none()

        if not user or not verify_password(plain_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Please contact the administrator.",
            )

        access_token, _, expires_in = create_access_token(
            subject=str(user.id), role="order_desk"
        )
        refresh_token, _, refresh_expires_at = create_refresh_token(
            subject=str(user.id), role="order_desk"
        )

        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=DeskUserInfo(
                id=str(user.id),
                full_name=user.full_name,
                email=user.email,
                role="order_desk",
            ),
        )
        return token_response, refresh_token, refresh_expires_at

    @staticmethod
    def refresh_tokens(
        db: Session, raw_refresh_token: str
    ) -> Tuple[TokenResponse, str, datetime]:
        """
        Validates refresh token, rotates JTI into blocklist, and issues new tokens.
        """
        try:
            payload = decode_token(raw_refresh_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        jti = payload.get("jti")
        sub = payload.get("sub")
        role = payload.get("role")

        if not jti or not sub or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token claims",
            )

        # Check blocklist
        block_stmt = select(RefreshTokenBlocklist).where(
            RefreshTokenBlocklist.jti == jti
        )
        if db.execute(block_stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

        # Verify subject still exists and is active
        retailer_info: Optional[RetailerInfo] = None
        desk_info: Optional[DeskUserInfo] = None

        if role == "retailer":
            r_stmt = select(Retailer).where(
                Retailer.id == sub, Retailer.is_active.is_(True)
            )
            retailer = db.execute(r_stmt).scalar_one_or_none()
            if not retailer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Retailer account inactive or not found",
                )
            retailer_info = RetailerInfo(
                id=str(retailer.id),
                name=retailer.name,
                mobile=retailer.mobile,
                address=retailer.address,
            )
        elif role == "order_desk":
            d_stmt = select(OrderDeskUser).where(
                OrderDeskUser.id == sub, OrderDeskUser.is_active.is_(True)
            )
            desk_user = db.execute(d_stmt).scalar_one_or_none()
            if not desk_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Order desk account inactive or not found",
                )
            desk_info = DeskUserInfo(
                id=str(desk_user.id),
                full_name=desk_user.full_name,
                email=desk_user.email,
                role="order_desk",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role"
            )

        # Blocklist old refresh token
        exp_timestamp = payload.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            if exp_timestamp
            else datetime.now(timezone.utc) + timedelta(days=7)
        )
        blocklisted = RefreshTokenBlocklist(jti=jti, expires_at=exp_dt)
        db.add(blocklisted)

        # Issue new rotated tokens
        new_access_token, _, expires_in = create_access_token(
            subject=sub, role=role
        )
        new_refresh_token, _, new_refresh_expires_at = create_refresh_token(
            subject=sub, role=role
        )

        db.commit()

        token_response = TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=expires_in,
            retailer=retailer_info,
            user=desk_info,
        )
        return token_response, new_refresh_token, new_refresh_expires_at

    @staticmethod
    def revoke_refresh_token(
        db: Session, raw_refresh_token: Optional[str]
    ) -> None:
        """
        Invalidates a refresh token by adding its JTI to the blocklist.
        """
        if not raw_refresh_token:
            return

        try:
            payload = decode_token(raw_refresh_token)
            jti = payload.get("jti")
            exp_timestamp = payload.get("exp")
            if jti:
                exp_dt = (
                    datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    if exp_timestamp
                    else datetime.now(timezone.utc) + timedelta(days=7)
                )
                db.add(RefreshTokenBlocklist(jti=jti, expires_at=exp_dt))
                db.commit()
        except Exception:
            pass

