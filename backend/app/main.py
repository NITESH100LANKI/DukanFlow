"""
FastAPI application factory for DukaanFlow.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.catalogue import router as catalogue_router
from app.api.cart import router as cart_router
from app.api.orders import router as orders_router
from app.api.desk_orders import router as desk_orders_router
from app.api.desk_exports import router as desk_exports_router
from app.api.ai import router as ai_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Performs critical production security validations on startup.
    """
    if settings.ENVIRONMENT == "production":
        if settings.DEMO_MODE:
            raise RuntimeError(
                "Fatal startup error: DEMO_MODE must be False in production environment."
            )
        if not settings.is_sms_configured:
            logger.warning(
                "Fast2SMS provider is not fully configured in production. "
                "Retailer OTP authentication will return HTTP 503 until "
                "FAST2SMS_API_KEY and FAST2SMS_OTP_ID are configured in environment."
            )
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,   # Disable Swagger in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS configuration supporting development, Vercel preview deploys, and custom production domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,         # Required for HttpOnly refresh cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Checksum-SHA256", "Content-Disposition"],
)

# Root health endpoints (for platform probes: Render, AWS, Kubernetes)
app.include_router(health_router)

# Versioned API v1 routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(catalogue_router, prefix=settings.API_V1_PREFIX)
app.include_router(cart_router, prefix=settings.API_V1_PREFIX)
app.include_router(orders_router, prefix=settings.API_V1_PREFIX)
app.include_router(desk_orders_router, prefix=settings.API_V1_PREFIX)
app.include_router(desk_exports_router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_router, prefix=settings.API_V1_PREFIX)
