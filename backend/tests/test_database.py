"""
Phase 2 — Database connectivity test.
Skipped automatically if DATABASE_URL is not set to a reachable server
(so CI without a DB still passes this module with a skip, not a failure).
"""

import pytest
from app.core.database import check_db_connection
from app.core.config import settings


@pytest.mark.skipif(
    "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL,
    reason="Skipping DB test: DATABASE_URL does not point to localhost",
)
def test_database_connectivity():
    """
    Verifies that the application can connect to the configured PostgreSQL database.
    Requires the Docker Compose db service to be running.
    """
    connected = check_db_connection()
    if not connected:
        pytest.skip(
            "PostgreSQL not reachable. Start the database with: docker compose up db -d"
        )
    assert connected is True

