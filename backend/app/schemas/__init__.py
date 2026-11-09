"""
Schemas export package.
"""

from app.schemas.auth import (
    RequestOTPRequest,
    RequestOTPResponse,
    VerifyOTPRequest,
    RetailerInfo,
    DeskUserInfo,
    TokenResponse,
    DeskLoginRequest,
    LogoutResponse,
    CurrentUserResponse,
)

__all__ = [
    "RequestOTPRequest",
    "RequestOTPResponse",
    "VerifyOTPRequest",
    "RetailerInfo",
    "DeskUserInfo",
    "TokenResponse",
    "DeskLoginRequest",
    "LogoutResponse",
    "CurrentUserResponse",
]

