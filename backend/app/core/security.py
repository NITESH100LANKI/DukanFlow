"""
Security utilities: password and OTP hashing, JWT encoding and decoding.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a bcrypt hash for a given password."""
    return bcrypt.hashpw(
        password.encode("utf-8")[:72], bcrypt.gensalt()
    ).decode("utf-8")


def hash_otp(otp: str) -> str:
    """Generates a bcrypt hash for an OTP."""
    return bcrypt.hashpw(otp.encode("utf-8")[:72], bcrypt.gensalt()).decode(
        "utf-8"
    )


def verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
    """Verifies a plain-text OTP against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_otp.encode("utf-8")[:72], hashed_otp.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, int]:
    """
    Creates a signed JWT access token.
    Returns: (token_str, jti, expires_in_seconds)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    expires_in = int((expire - now).total_seconds())
    return token, jti, expires_in


def create_refresh_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, datetime]:
    """
    Creates a signed JWT refresh token.
    Returns: (token_str, jti, expires_at_datetime)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "jti": jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, jti, expire


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT token. Raises JWTError if invalid or expired.
    """
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
