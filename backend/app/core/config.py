"""
Application configuration loaded from environment variables.
Never hard-code secrets — always use environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
    GEMINI_MODEL: str = "gemini-1.5-flash"
    AI_TIMEOUT_SECONDS: int = 10

    # Demo mode — OTP
    DEMO_MODE: bool = True              # If True, OTP is always "123456"
    DEMO_OTP: str = "123456"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

