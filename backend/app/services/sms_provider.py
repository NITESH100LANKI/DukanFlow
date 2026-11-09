"""
Fast2SMS Smart OTP Provider Integration for DukaanFlow (Phase 10).

Integrates with Fast2SMS Smart OTP API (POST https://www.fast2sms.com/dev/otp/send)
to deliver backend-generated 6-digit OTPs directly to retailer mobile devices.

Security & Architecture:
- Uses backend-generated cryptographically secure OTPs (preserving hashed OTPRecord storage)
- Asynchronous HTTP requests using httpx.AsyncClient
- Strict timeout and connection management
- Zero sensitive credential logging (API key, OTP code, and full mobile numbers are never logged)
- Zero automatic retries to prevent duplicate SMS delivery or burning credits
- Safe error handling and mapping to domain exceptions
"""

import logging
import re
from typing import Optional, Dict, Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSProviderError(Exception):
    """Base exception for all SMS delivery errors."""
    pass


class SMSProviderConfigurationError(SMSProviderError):
    """Raised when Fast2SMS credentials or template IDs are missing or invalid."""
    pass


class SMSTimeoutError(SMSProviderError):
    """Raised when the Fast2SMS API request times out."""
    pass


class SMSDeliveryError(SMSProviderError):
    """Raised when Fast2SMS API returns a delivery failure or unexpected status."""
    pass


def sanitize_failure_reason(raw_reason: Optional[str]) -> str:
    """
    Sanitizes raw error strings or exceptions to ensure no plain OTP values,
    full mobile numbers, or API keys are ever stored or returned.
    """
    if not raw_reason:
        return "Unknown SMS delivery failure"
    text = str(raw_reason).strip()
    # Mask full 10-12 digit phone numbers
    text = re.sub(r"\b\d{10,12}\b", "[PHONE_REDACTED]", text)
    # Mask 6-digit plain OTPs
    text = re.sub(r"\b\d{6}\b", "[OTP_REDACTED]", text)
    # Mask potential API keys or token strings (>20 continuous alnum chars)
    text = re.sub(r"\b[A-Za-z0-9_-]{20,}\b", "[SECRET_REDACTED]", text)
    # Enforce safe length limit
    return text[:255]


class Fast2SMSProvider:
    """
    Asynchronous client for Fast2SMS Smart OTP delivery.
    Endpoint: POST https://www.fast2sms.com/dev/otp/send
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        otp_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.FAST2SMS_API_KEY
        self.otp_id = otp_id if otp_id is not None else settings.FAST2SMS_OTP_ID
        self.base_url = base_url if base_url is not None else settings.FAST2SMS_BASE_URL
        self.timeout = timeout_seconds if timeout_seconds is not None else settings.FAST2SMS_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        """Returns True if both API key and OTP template ID are non-empty."""
        return bool(self.api_key and self.api_key.strip() and self.otp_id and self.otp_id.strip())

    @staticmethod
    def _mask_mobile(mobile: str) -> str:
        """Masks a mobile number for safe logging (e.g. 98****3210)."""
        if len(mobile) == 10:
            return f"{mobile[:2]}****{mobile[-4:]}"
        return "****"

    async def send_otp(self, mobile: str, otp: str) -> Dict[str, Any]:
        """
        Sends a backend-generated OTP to the given Indian mobile number via Fast2SMS.

        Parameters:
            mobile: 10-digit Indian mobile number (e.g. '9876543210')
            otp: 6-digit plain OTP string

        Returns:
            Dict containing Fast2SMS response metadata ('request_id', 'message')

        Raises:
            SMSProviderConfigurationError: If API key or template ID is missing
            SMSTimeoutError: If the HTTP request times out
            SMSDeliveryError: If Fast2SMS returns an error status or failure payload
        """
        if not self.is_configured():
            logger.error("Fast2SMS send_otp called but provider is not fully configured (missing key or otp_id).")
            raise SMSProviderConfigurationError("Fast2SMS API key or OTP template ID is not configured.")

        # Clean and validate mobile format (must be 10 digits starting with 6-9)
        clean_mobile = mobile.strip()
        if clean_mobile.startswith("+91"):
            clean_mobile = clean_mobile[3:]
        elif clean_mobile.startswith("91") and len(clean_mobile) == 12:
            clean_mobile = clean_mobile[2:]

        if not re.match(r"^[6-9]\d{9}$", clean_mobile):
            logger.warning("Fast2SMS rejected invalid mobile number format.")
            raise SMSDeliveryError("Invalid mobile number format. Expected 10-digit Indian mobile.")

        masked_mobile = self._mask_mobile(clean_mobile)
        logger.info("Initiating Fast2SMS OTP delivery for mobile %s", masked_mobile)

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "mobile": clean_mobile,
            "otp_id": self.otp_id,
            "otp": otp,
            "otp_expiry": 10,
            "otp_length": len(otp),
            "variables_values": otp,
        }

        try:
            # Dedicated client with strict timeout and no automatic retries
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.error("Fast2SMS OTP delivery timed out for %s after %ss", masked_mobile, self.timeout)
            raise SMSTimeoutError("Fast2SMS gateway timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Fast2SMS connection error for %s: %s", masked_mobile, type(exc).__name__)
            raise SMSDeliveryError("Fast2SMS network connection failure.") from exc

        # Handle non-200 HTTP responses
        if response.status_code == 401 or response.status_code == 412:
            logger.error("Fast2SMS authentication failure: HTTP %s", response.status_code)
            raise SMSProviderConfigurationError("Fast2SMS authentication failed. Invalid API key.")

        if response.status_code >= 400:
            error_detail = ""
            try:
                err_data = response.json()
                error_detail = err_data.get("message") or err_data.get("error") or ""
                if isinstance(error_detail, list):
                    error_detail = ", ".join(str(m) for m in error_detail)
            except Exception:
                error_detail = response.text[:100] if response.text else ""
            sanitized_err = sanitize_failure_reason(error_detail)
            logger.error("Fast2SMS gateway returned HTTP error %s: %s", response.status_code, sanitized_err)
            raise SMSDeliveryError(f"Fast2SMS gateway returned HTTP {response.status_code}: {sanitized_err}")

        # Parse JSON response
        try:
            data = response.json()
        except Exception as exc:
            logger.error("Fast2SMS returned non-JSON response for %s", masked_mobile)
            raise SMSDeliveryError("Malformed response received from Fast2SMS.") from exc

        # Fast2SMS Smart OTP protocol returns {"return": true/false, ...}
        # Validate both HTTP 200 AND internal return status
        is_successful = data.get("return") is True
        if not is_successful:
            error_message = data.get("message") or "Unknown delivery error"
            if isinstance(error_message, list):
                error_message = ", ".join(str(m) for m in error_message)
            logger.error(
                "Fast2SMS delivery rejected: status_code=%s, message=%s",
                data.get("status_code"),
                error_message,
            )
            raise SMSDeliveryError(f"Fast2SMS delivery error: {error_message}")

        request_id = data.get("request_id")
        if not request_id or not str(request_id).strip():
            logger.error("Fast2SMS returned return=true but missing valid request_id for %s", masked_mobile)
            raise SMSDeliveryError("Fast2SMS accepted delivery request but failed to return a valid request_id.")

        clean_request_id = str(request_id).strip()
        logger.info("Fast2SMS OTP successfully dispatched for %s (request_id=%s)", masked_mobile, clean_request_id)

        msg = data.get("message", "OTP sent successfully")
        if isinstance(msg, list):
            msg = ", ".join(str(m) for m in msg)

        return {
            "success": True,
            "request_id": clean_request_id,
            "message": msg,
        }
