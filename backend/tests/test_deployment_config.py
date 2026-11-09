"""
Unit and integration tests for Phase 9: Deployment Configuration, CORS Hardening, and Production Guards.
"""

import re
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.services.auth import AuthService
from app.main import app, lifespan


def test_cors_origins_validator():
    """Verify CORS_ORIGINS validator handles strings, JSON lists, and python lists."""
    s1 = Settings(CORS_ORIGINS="https://dukaanflow.vercel.app, https://example.com")
    assert s1.CORS_ORIGINS == ["https://dukaanflow.vercel.app", "https://example.com"]

    s2 = Settings(CORS_ORIGINS='["https://app.dukaanflow.in", "https://api.dukaanflow.in"]')
    assert s2.CORS_ORIGINS == ["https://app.dukaanflow.in", "https://api.dukaanflow.in"]

    s3 = Settings(CORS_ORIGINS=["https://custom.origin.com"])
    assert s3.CORS_ORIGINS == ["https://custom.origin.com"]


def test_cors_wildcard_forbidden_with_credentials():
    """Wildcard '*' must be strictly forbidden in CORS_ORIGINS to prevent credential exposure."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(CORS_ORIGINS="*")
    assert "CORS wildcard '*' is strictly forbidden" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info2:
        Settings(CORS_ORIGINS=["https://dukaanflow.vercel.app", "*"])
    assert "CORS wildcard '*' is strictly forbidden" in str(exc_info2.value)


def test_cors_preview_regex_restricted():
    """
    Verify strictly anchored regex allows DukaanFlow Vercel domains while
    rejecting phishing/attacker domains containing 'dukaanflow'.
    """
    settings = Settings()
    regex = re.compile(settings.CORS_ORIGIN_REGEX)

    # Valid origins
    assert regex.match("https://dukaanflow.vercel.app")
    assert regex.match("https://dukaanflow-git-feat-team.vercel.app")
    assert regex.match("https://dukaanflow-preview-123.vercel.app")
    assert regex.match("https://dukaanflow-a1b2c3d4.vercel.app")

    # Malicious / Attacker origins (MUST BE REJECTED)
    assert not regex.match("https://evil-dukaanflow.vercel.app")
    assert not regex.match("https://attacker-dukaanflow.vercel.app")
    assert not regex.match("https://notdukaanflow.vercel.app")
    assert not regex.match("https://dukaanflow.attacker.com")
    assert not regex.match("https://dukaanflow.vercel.app.phishing.com")
    assert not regex.match("http://dukaanflow.vercel.app")  # Plain HTTP rejected


def test_database_connection_pool_budget_defaults():
    """Verify conservative database connection pool defaults and configurability."""
    s = Settings(
        DB_POOL_SIZE=8,
        DB_MAX_OVERFLOW=4,
        DB_POOL_TIMEOUT=45,
        DB_POOL_RECYCLE=3600,
    )
    assert s.DB_POOL_SIZE == 8
    assert s.DB_MAX_OVERFLOW == 4
    assert s.DB_POOL_TIMEOUT == 45
    assert s.DB_POOL_RECYCLE == 3600

    # Default conservative sizing: 5 pool + 5 overflow = 10 per worker
    s_default = Settings()
    assert s_default.DB_POOL_SIZE == 5
    assert s_default.DB_MAX_OVERFLOW == 5


def test_cookie_secure_validator():
    """Verify COOKIE_SECURE handles boolean and string representations."""
    s1 = Settings(COOKIE_SECURE="true")
    assert s1.COOKIE_SECURE is True

    s2 = Settings(COOKIE_SECURE="false")
    assert s2.COOKIE_SECURE is False

    s3 = Settings(COOKIE_SECURE=True)
    assert s3.COOKIE_SECURE is True


@pytest.mark.asyncio
async def test_production_startup_guard_halts_on_demo_mode(monkeypatch):
    """Production startup must raise RuntimeError if DEMO_MODE is True in production."""
    from app.core import config
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)

    with pytest.raises(RuntimeError) as exc_info:
        async with lifespan(app):
            pass
    assert "DEMO_MODE must be False in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_production_startup_guard_succeeds_when_demo_mode_false(monkeypatch):
    """Production startup must succeed when DEMO_MODE is False in production."""
    from app.core import config
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)

    async with lifespan(app):
        # Startup succeeded
        assert config.settings.ENVIRONMENT == "production"
        assert config.settings.DEMO_MODE is False


def test_production_guard_rejects_demo_mode(monkeypatch):
    """Production guard must raise HTTP 500 if DEMO_MODE is True in production."""
    from app.core import config
    from app.core.database import SessionLocal

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            AuthService.request_otp(db, "9876543210")
        assert exc_info.value.status_code == 500
        assert "DEMO_MODE must be disabled in production" in exc_info.value.detail
    finally:
        db.close()


def test_production_guard_rejects_otp_without_real_provider(monkeypatch):
    """
    A boolean flag alone cannot bypass the absence of an SMS provider.
    Retailer OTP request in production MUST raise HTTP 503 even if SMS_PROVIDER_CONFIGURED is True.
    """
    from app.core import config
    from app.core.database import SessionLocal

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER_CONFIGURED", True)

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            AuthService.request_otp(db, "9876543210")
        assert exc_info.value.status_code == 503
        assert "Production SMS provider is not implemented" in exc_info.value.detail
    finally:
        db.close()


def test_cors_middleware_behavior_on_request():
    """Verify CORS middleware response headers across production, preview, and attacker origins."""
    with TestClient(app) as client:
        # 1. Allowed Production Origin
        res_prod = client.get("/health", headers={"Origin": "https://dukaanflow.vercel.app"})
        assert res_prod.status_code == 200
        assert res_prod.headers.get("access-control-allow-origin") == "https://dukaanflow.vercel.app"
        assert res_prod.headers.get("access-control-allow-credentials") == "true"

        # 2. Allowed DukaanFlow Preview Origin (via regex)
        res_preview = client.get(
            "/health", headers={"Origin": "https://dukaanflow-git-feat-xyz.vercel.app"}
        )
        assert res_preview.status_code == 200
        assert (
            res_preview.headers.get("access-control-allow-origin")
            == "https://dukaanflow-git-feat-xyz.vercel.app"
        )

        # 3. Disallowed Attacker Origin (must NOT receive CORS headers)
        res_attacker = client.get(
            "/health", headers={"Origin": "https://evil-dukaanflow.vercel.app"}
        )
        assert res_attacker.status_code == 200
        assert "access-control-allow-origin" not in res_attacker.headers

        # 4. Completely Unrelated Origin (must NOT receive CORS headers)
        res_unrelated = client.get("/health", headers={"Origin": "https://attacker.com"})
        assert res_unrelated.status_code == 200
        assert "access-control-allow-origin" not in res_unrelated.headers
