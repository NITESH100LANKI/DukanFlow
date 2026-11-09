"""
Health check endpoint — no authentication required.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db, check_db_connection
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """
    Returns application health status and database connectivity.
    Used by deployment platforms (Render, etc.) and monitoring tools.
    """
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "unreachable",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }

