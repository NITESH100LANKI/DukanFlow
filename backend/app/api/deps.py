"""
Authentication and role-based authorization dependencies for FastAPI endpoints.
"""

from typing import Annotated, Any, Callable, List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.auth import Retailer, OrderDeskUser

# Standard Bearer scheme
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Extracts, decodes, and validates the JWT Bearer access token.
    Returns the authenticated user details and database entity.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    role = payload.get("role")

    if not sub or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role == "retailer":
        stmt = select(Retailer).where(
            Retailer.id == sub, Retailer.is_active.is_(True)
        )
        retailer = db.execute(stmt).scalar_one_or_none()
        if not retailer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Retailer account not found or disabled",
            )
        return {
            "id": str(retailer.id),
            "role": "retailer",
            "name": retailer.name,
            "identifier": retailer.mobile,
            "entity": retailer,
        }

    elif role == "order_desk":
        stmt = select(OrderDeskUser).where(
            OrderDeskUser.id == sub, OrderDeskUser.is_active.is_(True)
        )
        desk_user = db.execute(stmt).scalar_one_or_none()
        if not desk_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Order Desk account not found or disabled",
            )
        return {
            "id": str(desk_user.id),
            "role": "order_desk",
            "name": desk_user.full_name,
            "identifier": desk_user.email,
            "entity": desk_user,
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid user role encoded in token",
    )


def require_role(allowed_roles: List[str]) -> Callable[..., dict[str, Any]]:
    """
    Dependency factory that checks whether the authenticated user has one of the allowed roles.
    """
    def role_checker(
        current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    ) -> dict[str, Any]:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: requires one of roles {allowed_roles}",
            )
        return current_user

    return role_checker

