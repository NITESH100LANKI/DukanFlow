"""
Phase 10.1 — Fast2SMS Production Reliability Audit & Security Tests.

Tests:
1. Fast2SMS Smart OTP payload delivery (HTTP 200 + return: true + valid request_id)
2. Fast2SMS Smart OTP payload contains: mobile, otp_id, otp, otp_expiry: 10, variables_values
3. Fast2SMS invalid API key handling (HTTP 401/412 -> 503)
4. Fast2SMS HTTP 200 with JSON failure (return: false -> 502)
5. Fast2SMS missing request ID (return: true but request_id missing/empty -> 502)
6. Fast2SMS gateway timeout handling without automatic retry (httpx.TimeoutException -> 504)
7. Fast2SMS HTTP 5xx server error handling (HTTP 500/503 -> 502)
8. Fast2SMS malformed non-JSON response handling (-> 502)
9. Zero OTP, API key, or complete phone logging (masked logs via caplog)
10. Delivery state workflow: PENDING -> SENT on success
11. Delivery state workflow: PENDING -> FAILED on rejection (with sanitized failure reason)
12. Delivery state workflow: PENDING -> UNKNOWN on timeout (ambiguous acceptance recorded, no retry)
13. Failed-delivery verification rejection (verification only accepts SENT records)
14. Expiry mismatch and expired OTP verification rejection (HTTP 401)
15. Database commit failure handling (clean rollback, HTTP 500)
16. Rate limiting: 3 requests per 10 minutes per mobile (HTTP 429)
17. Strike tracking: 5 failed attempts locks OTP (HTTP 423) and replay prevention
18. Settings configuration validation
"""

import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.core.config import Settings
from app.core.database import SessionLocal
from app.models.auth import Retailer, OTPRecord
from app.services.auth import AuthService
from app.services.sms_provider import (
    Fast2SMSProvider,
    SMSProviderConfigurationError,
    SMSTimeoutError,
    SMSDeliveryError,
    sanitize_failure_reason,
)


@pytest.fixture
def db_session():
    """Provides a transactional database session fixture for isolated tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_retailer(db_session: Session):
    """Creates a unique active test retailer for OTP verification."""
    while True:
        test_mobile = f"9{secrets.randbelow(900000000) + 100000000}"
        if not db_session.execute(select(Retailer).where(Retailer.mobile == test_mobile)).scalar_one_or_none():
            break

    retailer = Retailer(
        mobile=test_mobile,
        name="Patel Grocery Store",
        address="45 Station Road, Katni",
        credit_limit=75000.0,
        is_active=True,
    )
    db_session.add(retailer)
    db_session.commit()
    return retailer


# ==============================================================================
# 1. Fast2SMS Unit Tests (Direct Provider Client)
# ==============================================================================

@pytest.mark.asyncio
async def test_fast2sms_send_otp_success_payload(monkeypatch):
    """Fast2SMS sends Smart OTP payload with all required fields and valid request_id."""
    captured_requests = []

    async def mock_post(self, url, json=None, headers=None, **kwargs):
        captured_requests.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(
            status_code=200,
            json={
                "return": True,
                "request_id": "req_fast2sms_success_12345",
                "message": ["OTP sent successfully"],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(
        api_key="test_fast2sms_api_key_secret",
        otp_id="12345",
        base_url="https://www.fast2sms.com/dev/otp/send",
        timeout_seconds=5.0,
    )

    result = await provider.send_otp(mobile="9876543210", otp="654321")

    assert result["success"] is True
    assert result["request_id"] == "req_fast2sms_success_12345"

    # Verify complete payload specification
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["url"] == "https://www.fast2sms.com/dev/otp/send"
    assert req["headers"]["Authorization"] == "test_fast2sms_api_key_secret"
    assert req["json"]["mobile"] == "9876543210"
    assert req["json"]["otp"] == "654321"
    assert req["json"]["otp_id"] == "12345"
    assert req["json"]["otp_expiry"] == 10
    assert req["json"]["otp_length"] == 6
    assert req["json"]["variables_values"] == "654321"


@pytest.mark.asyncio
async def test_fast2sms_http_200_with_json_failure(monkeypatch):
    """HTTP 200 from provider with JSON return: false must be treated as failure."""
    async def mock_post(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"return": False, "status_code": 400, "message": "Invalid Template ID"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="key", otp_id="bad_template")
    with pytest.raises(SMSDeliveryError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "Invalid Template ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_missing_request_id(monkeypatch):
    """HTTP 200 with return: true but missing/empty request_id must raise SMSDeliveryError."""
    async def mock_post(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"return": True, "request_id": "", "message": ["Accepted"]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="key", otp_id="12345")
    with pytest.raises(SMSDeliveryError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "missing valid request_id" in str(exc_info.value) or "valid request_id" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_unconfigured_raises_error():
    """Unconfigured provider (missing key or template ID) raises SMSProviderConfigurationError."""
    provider = Fast2SMSProvider(api_key="", otp_id="")
    with pytest.raises(SMSProviderConfigurationError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_invalid_mobile_format():
    """Invalid mobile formats (non-Indian or wrong length) are rejected with SMSDeliveryError."""
    provider = Fast2SMSProvider(api_key="valid_key", otp_id="12345")
    with pytest.raises(SMSDeliveryError) as exc_info:
        await provider.send_otp(mobile="12345", otp="123456")
    assert "Invalid mobile number format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_invalid_api_key_401(monkeypatch):
    """HTTP 401 from Fast2SMS raises SMSProviderConfigurationError."""
    async def mock_post(self, url, **kwargs):
        return httpx.Response(status_code=401, json={"message": "Invalid API key"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="bad_key", otp_id="12345")
    with pytest.raises(SMSProviderConfigurationError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "Invalid API key" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_gateway_timeout(monkeypatch):
    """Fast2SMS timeout raises SMSTimeoutError without retrying."""
    call_count = 0

    async def mock_post(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="key", otp_id="12345")
    with pytest.raises(SMSTimeoutError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "timed out" in str(exc_info.value)
    assert call_count == 1, "Must never automatically retry an ambiguous timeout"


@pytest.mark.asyncio
async def test_fast2sms_gateway_500_error(monkeypatch):
    """Fast2SMS HTTP 500 error raises SMSDeliveryError."""
    async def mock_post(self, url, **kwargs):
        return httpx.Response(status_code=500, text="Internal Server Error", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="key", otp_id="12345")
    with pytest.raises(SMSDeliveryError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "HTTP 500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_malformed_json_response(monkeypatch):
    """Fast2SMS non-JSON response raises SMSDeliveryError."""
    async def mock_post(self, url, **kwargs):
        return httpx.Response(status_code=200, text="<html>Gateway Error</html>", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key="key", otp_id="12345")
    with pytest.raises(SMSDeliveryError) as exc_info:
        await provider.send_otp(mobile="9876543210", otp="123456")
    assert "Malformed response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fast2sms_zero_otp_or_key_logging(monkeypatch, caplog):
    """Verify that neither the plain OTP nor the API key is ever logged, and mobile is masked."""
    plain_secret_otp = "948216"
    secret_api_key = "super_secret_fast2sms_auth_key_xyz987"
    raw_mobile = "9876543210"

    async def mock_post(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"return": True, "request_id": "req_safe_log", "message": "Sent"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = Fast2SMSProvider(api_key=secret_api_key, otp_id="12345")

    with caplog.at_level(logging.DEBUG):
        await provider.send_otp(mobile=raw_mobile, otp=plain_secret_otp)

    all_logs = caplog.text

    assert plain_secret_otp not in all_logs, "CRITICAL: Plain OTP code was logged!"
    assert secret_api_key not in all_logs, "CRITICAL: Fast2SMS API key was logged!"
    assert raw_mobile not in all_logs, "CRITICAL: Full raw mobile number was logged!"
    assert "98****3210" in all_logs, "Expected masked mobile number 98****3210 in logs"


def test_sanitize_failure_reason():
    """Verify sanitize_failure_reason removes phone numbers, plain OTPs, and keys."""
    raw = "Failed for mobile 9876543210 with otp 123456 and key secret_api_key_1234567890abcdef"
    clean = sanitize_failure_reason(raw)
    assert "9876543210" not in clean
    assert "123456" not in clean
    assert "secret_api_key_1234567890abcdef" not in clean
    assert "[PHONE_REDACTED]" in clean
    assert "[OTP_REDACTED]" in clean
    assert "[SECRET_REDACTED]" in clean


# ==============================================================================
# 2. Delivery State Workflow & AuthService Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_auth_service_delivery_state_workflow_success(db_session: Session, test_retailer: Retailer, monkeypatch):
    """Successful dispatch updates state from PENDING to SENT and records provider_request_id."""
    async def mock_post_ok(self, url, json=None, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"return": True, "request_id": "req_audit_success_999", "message": "Dispatched"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_ok)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(config.settings, "FAST2SMS_API_KEY", "mock_key")
    monkeypatch.setattr(config.settings, "FAST2SMS_OTP_ID", "mock_otp_id")

    res = await AuthService.request_otp(db_session, test_retailer.mobile)
    assert res["message"] == "OTP sent"

    # Verify record in DB has delivery_status='SENT' and provider_request_id
    record = db_session.execute(
        select(OTPRecord).where(OTPRecord.mobile == test_retailer.mobile).order_by(OTPRecord.created_at.desc())
    ).scalar_one()

    assert record.delivery_status == "SENT"
    assert record.provider_request_id == "req_audit_success_999"
    assert record.failure_reason is None


@pytest.mark.asyncio
async def test_auth_service_delivery_state_workflow_failure(db_session: Session, test_retailer: Retailer, monkeypatch):
    """Failed dispatch marks record as FAILED with sanitized failure_reason."""
    async def mock_post_fail(self, url, **kwargs):
        return httpx.Response(
            status_code=400,
            json={"return": False, "message": "Invalid Template ID for 9876543210"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_fail)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(config.settings, "FAST2SMS_API_KEY", "mock_key")
    monkeypatch.setattr(config.settings, "FAST2SMS_OTP_ID", "mock_otp_id")

    with pytest.raises(HTTPException) as exc_info:
        await AuthService.request_otp(db_session, test_retailer.mobile)

    assert exc_info.value.status_code == 502

    # Verify record is marked FAILED in DB and stores sanitized failure reason
    record = db_session.execute(
        select(OTPRecord).where(OTPRecord.mobile == test_retailer.mobile).order_by(OTPRecord.created_at.desc())
    ).scalar_one()

    assert record.delivery_status == "FAILED"
    assert record.failure_reason is not None
    assert "9876543210" not in record.failure_reason
    assert "[PHONE_REDACTED]" in record.failure_reason


@pytest.mark.asyncio
async def test_auth_service_timeout_after_possible_acceptance(db_session: Session, test_retailer: Retailer, monkeypatch):
    """
    On timeout, provider may have accepted the SMS.
    System must transition status to UNKNOWN, never retry, and verify must reject it.
    """
    call_count = 0

    async def mock_post_timeout(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("Read timeout after 10s")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_timeout)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(config.settings, "FAST2SMS_API_KEY", "mock_key")
    monkeypatch.setattr(config.settings, "FAST2SMS_OTP_ID", "mock_otp_id")

    with pytest.raises(HTTPException) as exc_info:
        await AuthService.request_otp(db_session, test_retailer.mobile)

    assert exc_info.value.status_code == 504
    assert call_count == 1, "Must not retry ambiguous timeout"

    # Verify record is marked UNKNOWN
    record = db_session.execute(
        select(OTPRecord).where(OTPRecord.mobile == test_retailer.mobile).order_by(OTPRecord.created_at.desc())
    ).scalar_one()

    assert record.delivery_status == "UNKNOWN"
    assert "ambiguous" in record.failure_reason.lower()

    # Verification on UNKNOWN delivery status must be strictly rejected
    with pytest.raises(HTTPException) as verify_exc:
        AuthService.verify_otp(db_session, test_retailer.mobile, "123456")
    assert verify_exc.value.status_code == 401
    assert "not completed successfully" in verify_exc.value.detail


@pytest.mark.asyncio
async def test_auth_service_rejects_verification_of_failed_or_pending_delivery(
    db_session: Session, test_retailer: Retailer
):
    """Verification must only accept valid OTP records whose delivery was successfully accepted (SENT)."""
    from app.core.security import hash_otp

    # 1. Test PENDING record rejection
    pending_record = OTPRecord(
        mobile=test_retailer.mobile,
        otp_hash=hash_otp("111222"),
        attempts=0,
        locked=False,
        verified=False,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        delivery_status="PENDING",
    )
    db_session.add(pending_record)
    db_session.commit()

    with pytest.raises(HTTPException) as exc1:
        AuthService.verify_otp(db_session, test_retailer.mobile, "111222")
    assert exc1.value.status_code == 401
    assert "not completed successfully" in exc1.value.detail

    # 2. Test FAILED record rejection
    pending_record.delivery_status = "FAILED"
    pending_record.failure_reason = "Simulated provider failure"
    db_session.commit()

    with pytest.raises(HTTPException) as exc2:
        AuthService.verify_otp(db_session, test_retailer.mobile, "111222")
    assert exc2.value.status_code == 401
    assert "not completed successfully" in exc2.value.detail


@pytest.mark.asyncio
async def test_auth_service_expiry_mismatch_rejected(db_session: Session, test_retailer: Retailer):
    """An expired OTP record (past 10 minutes) must be rejected with HTTP 401."""
    from app.core.security import hash_otp

    expired_record = OTPRecord(
        mobile=test_retailer.mobile,
        otp_hash=hash_otp("999888"),
        attempts=0,
        locked=False,
        verified=False,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # Expired 1 min ago
        delivery_status="SENT",
    )
    db_session.add(expired_record)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_otp(db_session, test_retailer.mobile, "999888")
    assert exc_info.value.status_code == 401
    assert "Invalid or expired OTP" in exc_info.value.detail


@pytest.mark.asyncio
async def test_auth_service_database_commit_failure_handled(
    db_session: Session, test_retailer: Retailer, monkeypatch
):
    """Database commit failure during initial record creation triggers clean rollback and HTTP 500."""
    def broken_commit():
        raise Exception("Disk I/O error or constraint violation")

    monkeypatch.setattr(db_session, "commit", broken_commit)

    with pytest.raises(HTTPException) as exc_info:
        await AuthService.request_otp(db_session, test_retailer.mobile)
    assert exc_info.value.status_code == 500
    assert "Database error" in exc_info.value.detail


@pytest.mark.asyncio
async def test_auth_service_successful_otp_lifecycle_and_replay_protection(
    db_session: Session, test_retailer: Retailer, monkeypatch
):
    """
    Complete lifecycle with Fast2SMS:
    1. Send OTP -> dispatched via Fast2SMS with delivery_status='SENT'
    2. 5 wrong attempts -> locks OTP (HTTP 423)
    3. New OTP -> verified successfully
    4. Replay of same OTP -> rejected (HTTP 401 / 423)
    """
    dispatched_otps = []

    async def mock_post_success(self, url, json=None, **kwargs):
        dispatched_otps.append(json["otp"])
        return httpx.Response(
            status_code=200,
            json={"return": True, "request_id": f"req_{len(dispatched_otps)}"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_success)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(config.settings, "FAST2SMS_API_KEY", "mock_key")
    monkeypatch.setattr(config.settings, "FAST2SMS_OTP_ID", "mock_otp_id")

    # 1. Send OTP #1
    res1 = await AuthService.request_otp(db_session, test_retailer.mobile)
    assert res1["message"] == "OTP sent"
    assert len(dispatched_otps) == 1
    first_otp = dispatched_otps[0]
    assert len(first_otp) == 6

    # 2. Five failed verification attempts lock the record
    for attempt in range(1, 5):
        with pytest.raises(HTTPException) as exc_info:
            AuthService.verify_otp(db_session, test_retailer.mobile, "000000")
        assert exc_info.value.status_code == 401
        assert f"{5 - attempt} attempt(s) remaining" in exc_info.value.detail

    # 5th failed attempt triggers HTTP 423 Locked
    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_otp(db_session, test_retailer.mobile, "000000")
    assert exc_info.value.status_code == 423
    assert "OTP is locked" in exc_info.value.detail

    # 3. Request OTP #2
    res2 = await AuthService.request_otp(db_session, test_retailer.mobile)
    assert res2["message"] == "OTP sent"
    assert len(dispatched_otps) == 2
    second_otp = dispatched_otps[1]

    # Verify with correct OTP
    token_resp, refresh_token, expires_at = AuthService.verify_otp(db_session, test_retailer.mobile, second_otp)
    assert token_resp.access_token is not None
    assert token_resp.retailer is not None
    assert token_resp.retailer.mobile == test_retailer.mobile

    # 4. Replay prevention: reusing the same OTP must fail with HTTP 401 (or 423 locked)
    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_otp(db_session, test_retailer.mobile, second_otp)
    assert exc_info.value.status_code in (401, 423)


@pytest.mark.asyncio
async def test_auth_service_rate_limiting_3_per_10_minutes(
    db_session: Session, test_retailer: Retailer, monkeypatch
):
    """Max 3 OTP requests allowed per mobile number per 10-minute window."""
    async def mock_post_success(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            json={"return": True, "request_id": "req_rate"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_success)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(config.settings, "FAST2SMS_API_KEY", "mock_key")
    monkeypatch.setattr(config.settings, "FAST2SMS_OTP_ID", "mock_otp_id")

    # 3 successive requests should succeed
    for _ in range(3):
        res = await AuthService.request_otp(db_session, test_retailer.mobile)
        assert res["message"] == "OTP sent"

    # 4th request must be rejected with HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        await AuthService.request_otp(db_session, test_retailer.mobile)
    assert exc_info.value.status_code == 429
    assert "Too many OTP requests" in exc_info.value.detail


def test_settings_sms_configuration_property():
    """Verify is_sms_configured property logic."""
    # Default unconfigured
    s_default = Settings()
    assert s_default.is_sms_configured is False

    # Partial configuration
    s_partial1 = Settings(SMS_PROVIDER="fast2sms", FAST2SMS_API_KEY="key", FAST2SMS_OTP_ID="")
    assert s_partial1.is_sms_configured is False

    s_partial2 = Settings(SMS_PROVIDER="fast2sms", FAST2SMS_API_KEY="", FAST2SMS_OTP_ID="tmpl")
    assert s_partial2.is_sms_configured is False

    s_disabled = Settings(SMS_PROVIDER="disabled", FAST2SMS_API_KEY="key", FAST2SMS_OTP_ID="tmpl")
    assert s_disabled.is_sms_configured is False

    # Fully configured
    s_valid = Settings(SMS_PROVIDER="fast2sms", FAST2SMS_API_KEY="real_key", FAST2SMS_OTP_ID="real_otp_id")
    assert s_valid.is_sms_configured is True
