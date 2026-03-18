from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200


def test_health_returns_uptime_seconds():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_validation_error_includes_body():
    response = client.post("/api/items", json={"invalid": "data"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data  # Custom handler adds body field


def test_unhandled_exception_returns_generic_500():
    @app.get("/_test/raise-error")
    async def raise_error():
        raise RuntimeError("This is an unhandled exception")

    error_client = TestClient(app, raise_server_exceptions=False)
    response = error_client.get("/_test/raise-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
