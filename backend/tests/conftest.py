"""
Pytest configuration and shared fixtures for DukaanFlow backend tests.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import check_db_connection


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    FastAPI TestClient — reused for the full test session.
    Does not require a live database for health endpoint tests.
    """
    with TestClient(app) as c:
        yield c

