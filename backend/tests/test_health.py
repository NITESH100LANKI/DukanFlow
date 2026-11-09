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


def test_root_health_and_probe_endpoints(client):
    """Deployment probes at root (/health, /ready, /live) must function correctly."""
    # Root /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    assert res_health.json()["db"] == "connected"

    # Root /ready
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ok"

    # Root /live (liveness does not check DB)
    res_live = client.get("/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"


def test_health_degraded_when_db_down(client, monkeypatch):
    """Health check must return 503 and degraded status when database is unreachable."""
    monkeypatch.setattr("app.api.health.check_db_connection", lambda: False)
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "unreachable"

