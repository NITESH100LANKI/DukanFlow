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
from app.schemas.catalogue import (
    SchemeRead,
    ProductRead,
    ProductListResponse,
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
    "SchemeRead",
    "ProductRead",
    "ProductListResponse",
]

