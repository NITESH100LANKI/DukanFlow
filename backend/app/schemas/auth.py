"""
Pydantic schemas for Authentication request and response validation.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RequestOTPRequest(BaseModel):
    """Payload to request an OTP for retailer mobile login."""
    mobile: str = Field(
        ...,
        min_length=10,
        max_length=15,
        pattern=r"^\+?[0-9]{10,14}$",
        description="Mobile number with optional leading +",
    )


class RequestOTPResponse(BaseModel):
    """Response returned after requesting an OTP."""
    message: str = "OTP sent"
    expires_in_seconds: int = 600


class VerifyOTPRequest(BaseModel):
    """Payload to verify OTP and obtain access token."""
    mobile: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=4, max_length=10)


class RetailerInfo(BaseModel):
    """Public retailer profile data in auth response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    mobile: str
    address: Optional[str] = None


class DeskUserInfo(BaseModel):
    """Public Order Desk user profile data in auth response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str
    role: str = "order_desk"


class TokenResponse(BaseModel):
    """JWT Token response payload."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    retailer: Optional[RetailerInfo] = None
    user: Optional[DeskUserInfo] = None


class DeskLoginRequest(BaseModel):
    """Order Desk email and password login payload."""
    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Valid email address",
    )
    password: str = Field(..., min_length=1, max_length=128)


class LogoutResponse(BaseModel):
    """Logout confirmation payload."""
    message: str = "Logged out"


class CurrentUserResponse(BaseModel):
    """Current authenticated user profile."""
    id: str
    role: str
    name: str
    identifier: str
