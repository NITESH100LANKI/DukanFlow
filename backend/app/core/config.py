"""
Application configuration loaded from environment variables.
Never hard-code secrets — always use environment variables or .env file.
"""

from functools import lru_cache
from pathlib import Path
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

    # Application
    APP_NAME: str = "DukaanFlow"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://dukaanflow:dukaanflow@localhost:5432/dukaanflow"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie
    COOKIE_SECURE: bool = True          # Set False for local HTTP dev
    COOKIE_SAMESITE: str = "strict"     # "strict" | "lax" | "none"
    COOKIE_DOMAIN: str | None = None    # None = current host

    # AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_USE_INTERACTIONS_API: bool = False
    AI_TIMEOUT_SECONDS: int = 15

    # Demo mode — OTP
    DEMO_MODE: bool = True              # If True, OTP is always "123456"
    DEMO_OTP: str = "123456"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

