"""
Unit and integration tests for Phase 9: Deployment Configuration, CORS Hardening, and Production Guards.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.services.auth import AuthService
from app.main import app, lifespan


def test_cors_origins_validator():
    """Verify CORS_ORIGINS validator handles strings, JSON lists, and python lists in development."""
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


def test_cors_environment_specific_defaults():
    """
    Verify environment-specific CORS policies:
    - Development: defaults to localhost dev servers
    - Production: defaults strictly to actual production frontend origin
    - Production: disables preview regexes
    """
    # Development defaults
    s_dev = Settings(ENVIRONMENT="development")
    assert "http://localhost:5173" in s_dev.CORS_ORIGINS
    assert "http://localhost:3000" in s_dev.CORS_ORIGINS
    assert s_dev.CORS_ORIGIN_REGEX is None

    # Production defaults
    s_prod = Settings(ENVIRONMENT="production")
    assert s_prod.CORS_ORIGINS == ["https://dukaanflow.vercel.app"]
    assert "http://localhost:5173" not in s_prod.CORS_ORIGINS
    assert "http://localhost:3000" not in s_prod.CORS_ORIGINS
    assert s_prod.CORS_ORIGIN_REGEX is None


def test_cors_production_rejects_localhost():
    """Production configuration must reject explicit localhost origins."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS="https://dukaanflow.vercel.app, http://localhost:5173",
        )
    assert "Localhost origins" in str(exc_info.value)
    assert "strictly forbidden in production" in str(exc_info.value)


def test_cors_production_forces_preview_regex_disabled():
    """Production configuration must never enable arbitrary preview regexes."""
    s = Settings(
        ENVIRONMENT="production",
        CORS_ORIGIN_REGEX=r"^https://.*\.vercel\.app$",
    )
    assert s.CORS_ORIGIN_REGEX is None


def test_database_connection_pool_budget_and_workers():
    """
    Verify conservative database connection pool defaults, worker concurrency,
    and total calculated connection budget.
    """
    s_default = Settings()
    assert s_default.WEB_CONCURRENCY == 2
    assert s_default.DB_POOL_SIZE == 5
    assert s_default.DB_MAX_OVERFLOW == 5
    assert s_default.DB_POOL_TIMEOUT == 30
    assert s_default.DB_POOL_RECYCLE == 1800

    # Total connection budget calculation:
    # 1 instance * 2 workers * (5 pool + 5 overflow) = 20 maximum connections
    total_connections = 1 * s_default.WEB_CONCURRENCY * (s_default.DB_POOL_SIZE + s_default.DB_MAX_OVERFLOW)
    assert total_connections == 20

    # Configurable override check
    s_custom = Settings(
        WEB_CONCURRENCY=3,
        DB_POOL_SIZE=8,
        DB_MAX_OVERFLOW=4,
        DB_POOL_TIMEOUT=45,
        DB_POOL_RECYCLE=3600,
    )
    assert s_custom.WEB_CONCURRENCY == 3
    assert s_custom.DB_POOL_SIZE == 8
    assert s_custom.DB_MAX_OVERFLOW == 4
    assert s_custom.DB_POOL_TIMEOUT == 45
    assert s_custom.DB_POOL_RECYCLE == 3600


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


def test_cors_production_middleware_behavior():
    """
    Verify production CORS middleware accepts ONLY the actual production origin
    and strictly rejects localhost, unlisted preview, and attacker origins.
    """
    prod_settings = Settings(ENVIRONMENT="production")
    assert prod_settings.CORS_ORIGINS == ["https://dukaanflow.vercel.app"]
    assert prod_settings.CORS_ORIGIN_REGEX is None

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=prod_settings.CORS_ORIGINS,
        allow_origin_regex=prod_settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
    )

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(test_app) as client:
        # 1. Allowed Production Origin
        res_prod = client.get("/health", headers={"Origin": "https://dukaanflow.vercel.app"})
        assert res_prod.status_code == 200
        assert res_prod.headers.get("access-control-allow-origin") == "https://dukaanflow.vercel.app"
        assert res_prod.headers.get("access-control-allow-credentials") == "true"

        # 2. Localhost Origin in Production (MUST BE REJECTED)
        res_local = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert res_local.status_code == 200
        assert "access-control-allow-origin" not in res_local.headers

        # 3. Unlisted Preview Origin (MUST BE REJECTED — must use same-origin proxy)
        res_preview = client.get(
            "/health", headers={"Origin": "https://dukaanflow-git-feat-xyz.vercel.app"}
        )
        assert res_preview.status_code == 200
        assert "access-control-allow-origin" not in res_preview.headers

        # 4. Attacker Origin (MUST BE REJECTED)
        res_attacker = client.get(
            "/health", headers={"Origin": "https://evil-dukaanflow.vercel.app"}
        )
        assert res_attacker.status_code == 200
        assert "access-control-allow-origin" not in res_attacker.headers


def test_cors_development_middleware_behavior():
    """
    Verify development CORS middleware allows local development ports
    while rejecting arbitrary third-party origins.
    """
    dev_settings = Settings(ENVIRONMENT="development")
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=dev_settings.CORS_ORIGINS,
        allow_origin_regex=dev_settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
    )

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(test_app) as client:
        # Localhost Vite dev server (ALLOWED IN DEVELOPMENT)
        res_local = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert res_local.status_code == 200
        assert res_local.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert res_local.headers.get("access-control-allow-credentials") == "true"

        # Arbitrary origin (REJECTED IN DEVELOPMENT)
        res_evil = client.get("/health", headers={"Origin": "https://malicious-site.com"})
        assert res_evil.status_code == 200
        assert "access-control-allow-origin" not in res_evil.headers
