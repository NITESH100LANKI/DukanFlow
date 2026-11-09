"""
Comprehensive Phase 3 Integration & Unit Tests for Authentication & Authorization:
- Retailer OTP request & verification
- Attempt tracking & 5-strike lockout (HTTP 423)
- Rate limiting (HTTP 429)
- Order Desk email/password login
- Refresh token rotation & blocklist revocation
- Role-based authorization & /auth/me
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash, hash_otp
from app.models.auth import Retailer, OrderDeskUser, OTPRecord, RefreshTokenBlocklist


@pytest.fixture
def db_session():
    """Provides a transactional database session fixture for test setup."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_users(db_session: Session):
    """Creates isolated test Retailer and Order Desk records."""
    test_mobile = f"98765{str(uuid.uuid4().int)[:5]}"
    test_email = f"desk_{str(uuid.uuid4().hex)[:6]}@dukaanflow.in"

    retailer = Retailer(
        mobile=test_mobile,
        name="Sharma Kirana Store",
        address="123 Gol Bazar, Jabalpur",
        credit_limit=50000.0,
        is_active=True,
    )
    desk_user = OrderDeskUser(
        email=test_email,
        password_hash=get_password_hash("DeskSecret123"),
        full_name="Rajesh Desk Manager",
        is_active=True,
    )
    disabled_desk_user = OrderDeskUser(
        email=f"disabled_{test_email}",
        password_hash=get_password_hash("DeskSecret123"),
        full_name="Inactive Staff",
        is_active=False,
    )

    db_session.add(retailer)
    db_session.add(desk_user)
    db_session.add(disabled_desk_user)
    db_session.commit()

    return {
        "retailer": retailer,
        "desk_user": desk_user,
        "disabled_desk_user": disabled_desk_user,
        "mobile": test_mobile,
        "email": test_email,
        "password": "DeskSecret123",
    }


def test_request_otp_nonexistent_retailer(client: TestClient):
    """Requesting OTP for an unregistered mobile must return 404."""
    response = client.post(
        "/api/v1/auth/retailer/request-otp",
        json={"mobile": "9999999999"},
    )
    assert response.status_code == 404
    assert "No active retailer account found" in response.json()["detail"]


def test_request_otp_success_and_rate_limiting(
    client: TestClient, seeded_users
):
    """Retailer can request OTP; 4th request within 10 min triggers 429."""
    mobile = seeded_users["mobile"]

    # First 3 requests must succeed
    for _ in range(3):
        res = client.post(
            "/api/v1/auth/retailer/request-otp",
            json={"mobile": mobile},
        )
        assert res.status_code == 200
        assert res.json()["message"] == "OTP sent"

    # 4th request must be rate limited
    fourth_res = client.post(
        "/api/v1/auth/retailer/request-otp",
        json={"mobile": mobile},
    )
    assert fourth_res.status_code == 429
    assert "Too many OTP requests" in fourth_res.json()["detail"]


def test_verify_otp_success(client: TestClient, seeded_users, db_session):
    """Submitting correct OTP issues access token and sets refresh cookie."""
    mobile = seeded_users["mobile"]
    plain_otp = "123456"

    # Create explicit active OTP record
    now = datetime.now(timezone.utc)
    otp_rec = OTPRecord(
        mobile=mobile,
        otp_hash=hash_otp(plain_otp),
        attempts=0,
        locked=False,
        verified=False,
        expires_at=now + timedelta(minutes=10),
    )
    db_session.add(otp_rec)
    db_session.commit()

    res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": plain_otp},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["retailer"]["mobile"] == mobile
    assert data["retailer"]["name"] == "Sharma Kirana Store"
    assert "refresh_token" in res.cookies


def test_verify_otp_invalid_and_lockout(
    client: TestClient, seeded_users, db_session
):
    """Failed verification increments attempts; 5th failure locks the OTP (HTTP 423)."""
    mobile = seeded_users["mobile"]
    now = datetime.now(timezone.utc)
    otp_rec = OTPRecord(
        mobile=mobile,
        otp_hash=hash_otp("123456"),
        attempts=0,
        locked=False,
        verified=False,
        expires_at=now + timedelta(minutes=10),
    )
    db_session.add(otp_rec)
    db_session.commit()

    # Attempts 1 to 4 return 401
    for i in range(1, 5):
        res = client.post(
            "/api/v1/auth/retailer/verify-otp",
            json={"mobile": mobile, "otp": "000000"},
        )
        assert res.status_code == 401
        assert f"{5 - i} attempt(s) remaining" in res.json()["detail"]

    # 5th attempt locks the OTP (HTTP 423)
    lock_res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": "000000"},
    )
    assert lock_res.status_code == 423
    assert "OTP is locked" in lock_res.json()["detail"]

    # Submitting the correct code now must still fail because it's locked
    correct_res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": "123456"},
    )
    assert correct_res.status_code == 423


def test_verify_otp_expired(client: TestClient, seeded_users, db_session):
    """Expired OTP records are rejected with 401."""
    mobile = seeded_users["mobile"]
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired_rec = OTPRecord(
        mobile=mobile,
        otp_hash=hash_otp("123456"),
        attempts=0,
        locked=False,
        verified=False,
        expires_at=past,
    )
    db_session.add(expired_rec)
    db_session.commit()

    res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": "123456"},
    )
    assert res.status_code == 401
    assert "Invalid or expired OTP" in res.json()["detail"]


def test_order_desk_login_success(client: TestClient, seeded_users):
    """Order desk staff can authenticate with email and password."""
    res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": seeded_users["password"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "order_desk"
    assert data["user"]["email"] == seeded_users["email"]
    assert "refresh_token" in res.cookies


def test_order_desk_login_invalid_password(client: TestClient, seeded_users):
    """Wrong password triggers 401."""
    res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": "WrongPassword!",
        },
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_order_desk_login_disabled_account(client: TestClient, seeded_users):
    """Disabled accounts are denied with 403 Forbidden."""
    disabled_user = seeded_users["disabled_desk_user"]
    res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": disabled_user.email,
            "password": seeded_users["password"],
        },
    )
    assert res.status_code == 403
    assert "Account is disabled" in res.json()["detail"]


def test_refresh_token_rotation_and_revocation(
    client: TestClient, seeded_users
):
    """Refresh token exchanges for a new token; old token is blocklisted."""
    # Login to get initial tokens
    login_res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": seeded_users["password"],
        },
    )
    assert login_res.status_code == 200
    initial_cookie = login_res.cookies["refresh_token"]

    # Call /auth/refresh with the initial cookie
    client.cookies.set("refresh_token", initial_cookie)
    refresh_res = client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    new_data = refresh_res.json()
    assert "access_token" in new_data
    rotated_cookie = refresh_res.cookies["refresh_token"]
    assert rotated_cookie != initial_cookie

    # Replay attack: try using the old initial cookie again -> 401 Blocklisted
    client.cookies.set("refresh_token", initial_cookie)
    replay_res = client.post("/api/v1/auth/refresh")
    assert replay_res.status_code == 401
    assert "Token has been revoked" in replay_res.json()["detail"]


def test_logout_and_revocation(client: TestClient, seeded_users):
    """Logout clears the cookie and revokes the refresh token."""
    login_res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": seeded_users["password"],
        },
    )
    token = login_res.json()["access_token"]
    cookie = login_res.cookies["refresh_token"]

    client.cookies.set("refresh_token", cookie)
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Logged out"

    # Verifying refresh after logout fails
    client.cookies.set("refresh_token", cookie)
    res_after = client.post("/api/v1/auth/refresh")
    assert res_after.status_code == 401


def test_get_current_user_me(client: TestClient, seeded_users):
    """Authenticated users can query /api/v1/auth/me."""
    # Test Retailer
    mobile = seeded_users["mobile"]
    login_res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": "123456"},
    )
    # If OTP was consumed in previous test, request one
    if login_res.status_code != 200:
        client.post(
            "/api/v1/auth/retailer/request-otp", json={"mobile": mobile}
        )
        login_res = client.post(
            "/api/v1/auth/retailer/verify-otp",
            json={"mobile": mobile, "otp": "123456"},
        )

    ret_token = login_res.json()["access_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["role"] == "retailer"
    assert me_data["identifier"] == mobile

    # Test without token -> 401
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401


def test_role_enforcement_retailer_cannot_access_desk(
    client: TestClient, seeded_users
):
    """Retailer token must be rejected with 403 Forbidden on desk-only routes."""
    mobile = seeded_users["mobile"]
    login_res = client.post(
        "/api/v1/auth/retailer/verify-otp",
        json={"mobile": mobile, "otp": "123456"},
    )
    if login_res.status_code != 200:
        client.post(
            "/api/v1/auth/retailer/request-otp", json={"mobile": mobile}
        )
        login_res = client.post(
            "/api/v1/auth/retailer/verify-otp",
            json={"mobile": mobile, "otp": "123456"},
        )
    ret_token = login_res.json()["access_token"]

    # Access retailer route -> 200
    allowed_res = client.get(
        "/api/v1/auth/retailer-only",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert allowed_res.status_code == 200

    # Access desk route -> 403 Forbidden
    forbidden_res = client.get(
        "/api/v1/auth/desk-only",
        headers={"Authorization": f"Bearer {ret_token}"},
    )
    assert forbidden_res.status_code == 403
    assert "Access denied" in forbidden_res.json()["detail"]


def test_role_enforcement_desk_cannot_access_retailer(
    client: TestClient, seeded_users
):
    """Order Desk token must be rejected with 403 Forbidden on retailer-only routes."""
    login_res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": seeded_users["password"],
        },
    )
    desk_token = login_res.json()["access_token"]

    # Access desk route -> 200
    allowed_res = client.get(
        "/api/v1/auth/desk-only",
        headers={"Authorization": f"Bearer {desk_token}"},
    )
    assert allowed_res.status_code == 200

    # Access retailer route -> 403 Forbidden
    forbidden_res = client.get(
        "/api/v1/auth/retailer-only",
        headers={"Authorization": f"Bearer {desk_token}"},
    )
    assert forbidden_res.status_code == 403
    assert "Access denied" in forbidden_res.json()["detail"]


def test_jwt_expired_token_rejected(client: TestClient, seeded_users):
    """Expired access token must return 401 Unauthorized."""
    from app.core.security import create_access_token

    expired_token, _, _ = create_access_token(
        subject=str(seeded_users["retailer"].id),
        role="retailer",
        expires_delta=timedelta(seconds=-10),
    )

    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "Invalid or expired access token" in res.json()["detail"]


def test_otp_non_demo_generates_random(client: TestClient, db_session: Session):
    """When DEMO_MODE is False, OTP must not be fixed 123456."""
    from app.core.config import settings
    from app.core.security import verify_otp_hash

    # Create temporary retailer
    rand_mobile = f"98765{str(uuid.uuid4().int)[:5]}"
    ret = Retailer(mobile=rand_mobile, name="Random OTP Test Store", is_active=True)
    db_session.add(ret)
    db_session.commit()

    original_mode = settings.DEMO_MODE
    try:
        settings.DEMO_MODE = False
        res = client.post(
            "/api/v1/auth/retailer/request-otp",
            json={"mobile": rand_mobile},
        )
        assert res.status_code == 200

        # Retrieve the OTP record
        stmt = (
            select(OTPRecord)
            .where(OTPRecord.mobile == rand_mobile)
            .order_by(OTPRecord.created_at.desc())
        )
        rec = db_session.execute(stmt).scalar_one()

        # The hashed OTP in DB must NOT match fixed demo OTP 123456
        assert not verify_otp_hash("123456", rec.otp_hash)
    finally:
        settings.DEMO_MODE = original_mode


def test_refresh_cookie_security_attributes(client: TestClient, seeded_users):
    """Refresh token cookie must contain HttpOnly, SameSite, and Path attributes."""
    res = client.post(
        "/api/v1/auth/desk/login",
        json={
            "email": seeded_users["email"],
            "password": seeded_users["password"],
        },
    )
    assert res.status_code == 200

    cookie_header = res.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/" in cookie_header
    assert "SameSite" in cookie_header

