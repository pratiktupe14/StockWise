from unittest.mock import patch
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test root endpoint returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "StockWise"
    assert "tagline" in data
    assert data["version"] == "0.1.0"
    assert data["health"] == "/api/health"


def test_health_endpoint_contract(client: TestClient):
    """Test /api/health endpoint structure and fields."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    # Core required fields
    assert "status" in data
    assert data["app_name"] == "StockWise"
    assert data["version"] == "0.1.0"
    assert data["api"] == "online"
    assert "timestamp" in data
    assert "environment" in data

    # Database health structure
    db = data["database"]
    assert "connected" in db
    assert "status" in db
    assert db["status"] in ["connected", "disconnected"]
    assert "message" in db
    assert "dialect" in db
    assert "latency_ms" in db


def test_health_alias_endpoint(client: TestClient):
    """Test /health alias routes to the same health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["api"] == "online"


def test_database_connected_state(client: TestClient):
    """Test health response when database is connected."""
    mock_db_result = {
        "connected": True,
        "message": "Successfully connected to postgresql database.",
        "dialect": "postgresql",
        "latency_ms": 4.5,
    }

    with patch("app.api.health.check_database_connection", return_value=mock_db_result):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
        assert data["database"]["status"] == "connected"
        assert data["database"]["latency_ms"] == 4.5


def test_database_disconnected_state(client: TestClient):
    """Test health response when database is unreachable."""
    mock_db_result = {
        "connected": False,
        "message": "Database unreachable: connection to server at 'localhost', port 5432 failed.",
        "dialect": "postgresql",
        "latency_ms": 3000.0,
    }

    with patch("app.api.health.check_database_connection", return_value=mock_db_result):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["connected"] is False
        assert data["database"]["status"] == "disconnected"
        assert "Database unreachable" in data["database"]["message"]


def test_cors_preflight(client: TestClient):
    """Test CORS headers for frontend origin."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
