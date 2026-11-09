"""
Application configuration loaded from environment variables.
Never hard-code secrets — always use environment variables or .env file.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(PROJECT_ROOT / ".env"),
            str(BACKEND_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"    # "development" | "staging" | "production"
    APP_NAME: str = "DukaanFlow"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://dukaanflow:dukaanflow@localhost:5432/dukaanflow"
    # Connection Pool Budget:
    # Total connections = (instances) * (workers) * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
    # Render Managed PostgreSQL Starter provides 97 available connections.
    # 1 instance * 2 workers * (5 + 5) = 20 connections max, leaving 77 headroom for CLI/migrations/probes.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie
    COOKIE_SECURE: bool = False         # False for local HTTP dev; True in production
    COOKIE_SAMESITE: str = "lax"        # "lax" | "strict" | "none"
    COOKIE_DOMAIN: Optional[str] = None # None = current host; or ".dukaanflow.in" for subdomains

    # CORS
    # In development: allows local dev servers ["http://localhost:5173", "http://localhost:3000"]
    # In production: strictly restricted to actual production frontend ["https://dukaanflow.vercel.app"]
    # Localhost origins and arbitrary preview regexes are forbidden in production.
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    # Set to None: no preview regex trust. Only explicit origins in CORS_ORIGINS are accepted.
    CORS_ORIGIN_REGEX: Optional[str] = None

    # Process Concurrency & Worker Budget
    # Exactly 2 workers per instance: 1 instance * 2 workers * (5 pool + 5 overflow) = 20 connections max.
    WEB_CONCURRENCY: int = 2

    # AI (Gemini — Text-based order extraction: Hindi, Hinglish, English)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_USE_INTERACTIONS_API: bool = False
    AI_TIMEOUT_SECONDS: int = 15

    # Retailer OTP & SMS Gateway
    DEMO_MODE: bool = True              # If True, OTP is fixed "123456" (DEV ONLY; FORBIDDEN IN PROD)
    DEMO_OTP: str = "123456"
    SMS_PROVIDER_CONFIGURED: bool = False  # Informational flag: SMS provider integration is pending

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        origins: List[str] = []
        if isinstance(v, str):
            if v.startswith("["):
                origins = json.loads(v)
            else:
                origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            origins = v
        else:
            origins = ["http://localhost:5173", "http://localhost:3000"]

        # Security requirement: Wildcard '*' cannot be combined with credentials (cookies)
        if "*" in origins:
            raise ValueError(
                "CORS wildcard '*' is strictly forbidden when credentials (cookies) are enabled. "
                "Specify explicit allowed origins."
            )
        return origins

    @model_validator(mode="after")
    def validate_cors_environment(self) -> "Settings":
        """
        Enforce strict environment-specific CORS policies:
        - In production, localhost origins are forbidden and stripped/rejected.
        - In production, defaults strictly to the production frontend origin.
        - In production, arbitrary preview regexes are disabled (None).
        - In development, localhost origins are permitted for local development.
        """
        if self.ENVIRONMENT == "production":
            localhost_origins = [
                o for o in self.CORS_ORIGINS
                if "localhost" in o or "127.0.0.1" in o
            ]
            if localhost_origins:
                # If CORS_ORIGINS is the default development list, replace with canonical production origin
                if set(self.CORS_ORIGINS) == {"http://localhost:5173", "http://localhost:3000"}:
                    self.CORS_ORIGINS = ["https://dukaanflow.vercel.app"]
                else:
                    raise ValueError(
                        f"Localhost origins {localhost_origins} are strictly forbidden in production CORS configuration."
                    )
            elif not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["https://dukaanflow.vercel.app"]

            # Arbitrary preview regexes must never be enabled in production
            self.CORS_ORIGIN_REGEX = None
        return self

    @field_validator("COOKIE_SECURE", mode="before")
    @classmethod
    def default_cookie_secure(cls, v: Any, values: Any) -> bool:
        if v is not None:
            if isinstance(v, str):
                return v.lower() in ("true", "1", "yes")
            return bool(v)
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
