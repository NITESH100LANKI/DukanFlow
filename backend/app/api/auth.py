"""
Authentication endpoints for Retailers and Order Desk staff.
"""

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import (
    RequestOTPRequest,
    RequestOTPResponse,
    VerifyOTPRequest,
    DeskLoginRequest,
    TokenResponse,
    LogoutResponse,
    CurrentUserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, token: str, expires_at: Any) -> None:
    """Sets a secure HttpOnly refresh token cookie on the HTTP response."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        expires=expires_at,
        path="/",
    )


@router.post(
    "/retailer/request-otp",
    response_model=RequestOTPResponse,
    summary="Request mobile OTP for retailer login",
)
async def request_retailer_otp(
    payload: RequestOTPRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates mobile number OTP verification for a retailer.
    In DEMO_MODE, the OTP is fixed to DEMO_OTP (123456).
    """
    res = await AuthService.request_otp(db, payload.mobile)
    return res


@router.post(
    "/retailer/verify-otp",
    response_model=TokenResponse,
    summary="Verify mobile OTP and obtain JWT tokens",
)
def verify_retailer_otp(
    payload: VerifyOTPRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Validates the submitted OTP. Upon success, returns an access token
    and sets an HttpOnly refresh token cookie.
    """
    token_resp, refresh_token, refresh_exp = AuthService.verify_otp(
        db, payload.mobile, payload.otp
    )
    set_refresh_cookie(response, refresh_token, refresh_exp)
    return token_resp


@router.post(
    "/desk/login",
    response_model=TokenResponse,
    summary="Order Desk email and password login",
)
def desk_login(
    payload: DeskLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates an Order Desk user with email and bcrypt-hashed password.
    Returns an access token and sets an HttpOnly refresh token cookie.
    """
    token_resp, refresh_token, refresh_exp = AuthService.desk_login(
        db, payload.email, payload.password
    )
    set_refresh_cookie(response, refresh_token, refresh_exp)
    return token_resp


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new access token",
)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Exchanges an active HttpOnly refresh token cookie for a new access token
    and a rotated refresh token. The previous refresh token JTI is blocklisted.
    """
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )

    token_resp, new_refresh_token, new_refresh_exp = AuthService.refresh_tokens(
        db, raw_token
    )
    set_refresh_cookie(response, new_refresh_token, new_refresh_exp)
    return token_resp


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout and revoke refresh token",
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
):
    """
    Revokes the current refresh token and deletes the refresh cookie.
    """
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        AuthService.revoke_refresh_token(db, raw_token)

    response.delete_cookie(
        key="refresh_token",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return LogoutResponse(message="Logged out")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
):
    """
    Returns profile information for the authenticated Retailer or Order Desk staff.
    """
    return CurrentUserResponse(
        id=current_user["id"],
        role=current_user["role"],
        name=current_user["name"],
        identifier=current_user["identifier"],
    )


@router.get(
    "/retailer-only",
    summary="Retailer role verification endpoint",
)
def check_retailer_role(
    current_user: Annotated[dict[str, Any], Depends(require_role(["retailer"]))],
):
    """Enforces retailer role access."""
    return {"message": "Retailer access granted", "role": current_user["role"]}


@router.get(
    "/desk-only",
    summary="Order Desk role verification endpoint",
)
def check_desk_role(
    current_user: Annotated[dict[str, Any], Depends(require_role(["order_desk"]))],
):
    """Enforces order desk role access."""
    return {"message": "Order Desk access granted", "role": current_user["role"]}

