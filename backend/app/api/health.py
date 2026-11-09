"""
Health and readiness probe endpoints — no authentication required.
Used by deployment platforms (Render, Kubernetes, uptime monitors).
"""

from fastapi import APIRouter, Response, status
from app.core.database import check_db_connection
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Application and database health check")
def health_check(response: Response):
    """
    Returns application health status and database connectivity.
    If the database is unreachable, returns HTTP 503 Service Unavailable.
    Never calls external AI APIs or exposes credentials/connection strings.
    """
    db_ok = check_db_connection()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "unreachable",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready", summary="Readiness probe for container orchestration")
def readiness_check(response: Response):
    """
    Readiness probe verifying database connectivity before routing traffic.
    Returns HTTP 503 if the database is not ready.
    """
    return health_check(response)


@router.get("/live", summary="Liveness probe for process vitality")
def liveness_check():
    """
    Liveness probe returning 200 if the Python web process is running.
    Does not ping downstream dependencies.
    """
    return {
        "status": "alive",
        "version": settings.APP_VERSION,
    }
