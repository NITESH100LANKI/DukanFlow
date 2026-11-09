"""
Phase 2 — Health endpoint tests.
"""


def test_health_endpoint_returns_200(client):
    """Health endpoint must always return 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_shape(client):
    """Health response must include required fields."""
    response = client.get("/api/v1/health")
    body = response.json()
    assert "status" in body
    assert "db" in body
    assert "version" in body
    assert "app" in body


def test_health_status_values(client):
    """Status must be 'ok' or 'degraded'; db must be 'connected' or 'unreachable'."""
    response = client.get("/api/v1/health")
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["db"] in ("connected", "unreachable")


def test_health_app_name(client):
    """App name must be 'DukaanFlow'."""
    response = client.get("/api/v1/health")
    body = response.json()
    assert body["app"] == "DukaanFlow"


def test_health_version_present(client):
    """Version must be a non-empty string."""
    response = client.get("/api/v1/health")
    body = response.json()
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0

