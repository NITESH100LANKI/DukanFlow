"""
Unit and integration tests for Phase 9: Deployment Configuration and Production Guards.
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.config import Settings
from app.services.auth import AuthService


def test_cors_origins_validator():
    """Verify CORS_ORIGINS validator handles strings, JSON lists, and python lists."""
    s1 = Settings(CORS_ORIGINS="https://dukaanflow.vercel.app, https://example.com")
    assert s1.CORS_ORIGINS == ["https://dukaanflow.vercel.app", "https://example.com"]

    s2 = Settings(CORS_ORIGINS='["https://app.dukaanflow.in", "https://api.dukaanflow.in"]')
    assert s2.CORS_ORIGINS == ["https://app.dukaanflow.in", "https://api.dukaanflow.in"]

    s3 = Settings(CORS_ORIGINS=["https://custom.origin.com"])
    assert s3.CORS_ORIGINS == ["https://custom.origin.com"]


def test_cookie_secure_validator():
    """Verify COOKIE_SECURE handles boolean and string representations."""
    s1 = Settings(COOKIE_SECURE="true")
    assert s1.COOKIE_SECURE is True

    s2 = Settings(COOKIE_SECURE="false")
    assert s2.COOKIE_SECURE is False

    s3 = Settings(COOKIE_SECURE=True)
    assert s3.COOKIE_SECURE is True


def test_production_guard_rejects_demo_mode(monkeypatch):
    """Production guard must raise HTTP 500 if DEMO_MODE is True in production."""
    from app.core import config
    from app.core.database import SessionLocal

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)

    db = SessionLocal()
    try:
        # Request OTP in production with DEMO_MODE enabled
        with pytest.raises(HTTPException) as exc_info:
            AuthService.request_otp(db, "9876543210")
        assert exc_info.value.status_code == 500
        assert "DEMO_MODE must be disabled in production" in exc_info.value.detail
    finally:
        db.close()


def test_production_guard_rejects_missing_sms_provider(monkeypatch):
    """Production guard must raise HTTP 503 if SMS provider is not configured."""
    from app.core import config
    from app.core.database import SessionLocal

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER_CONFIGURED", False)

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            AuthService.request_otp(db, "9876543210")
        assert exc_info.value.status_code == 503
        assert "SMS gateway is not configured" in exc_info.value.detail
    finally:
        db.close()
