from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient
    from main import app
    response = TestClient(app).get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "FastAPI Backend"
    assert "docs" in data
    assert "health" in data


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_validation_error_returns_422():
    response = client.post("/api/items", json={"price": "not-a-number"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_security_headers():
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "0"
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers.get("permissions-policy") is not None
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_unhandled_exception_returns_generic_500():
    from fastapi import FastAPI
    from main import generic_exception_handler

    isolated = FastAPI()
    isolated.add_exception_handler(Exception, generic_exception_handler)

    @isolated.get("/_test/raise-error")
    async def raise_error():
        raise RuntimeError("This is an unhandled exception")

    error_client = TestClient(isolated, raise_server_exceptions=False)
    response = error_client.get("/_test/raise-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_docs_inaccessible_in_production(monkeypatch):
    """Swagger UI, ReDoc, and OpenAPI schema are disabled when debug=False."""
    monkeypatch.setenv("DEBUG", "false")
    from importlib import reload
    import main as main_module

    reload(main_module)
    prod_client = TestClient(main_module.app)
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/redoc").status_code == 404
    assert prod_client.get("/openapi.json").status_code == 404


def test_docs_accessible_in_debug(monkeypatch):
    """Swagger UI, ReDoc, and OpenAPI schema are available when debug=True."""
    monkeypatch.setenv("DEBUG", "true")
    from importlib import reload
    import main as main_module

    reload(main_module)
    debug_client = TestClient(main_module.app)
    assert debug_client.get("/docs").status_code == 200
    assert debug_client.get("/redoc").status_code == 200
    assert debug_client.get("/openapi.json").status_code == 200


def test_hello_returns_message():
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello from FastAPI!"


def test_notify_returns_202():
    from unittest.mock import patch
    from fastapi import BackgroundTasks
    from main import send_notification_email

    recorded = []
    original_add_task = BackgroundTasks.add_task

    def spy_add_task(self, func, *args, **kwargs):
        recorded.append((func, args, kwargs))
        return original_add_task(self, func, *args, **kwargs)

    with patch.object(BackgroundTasks, "add_task", spy_add_task):
        response = client.post(
            "/api/v1/notify",
            json={"email": "test@example.com", "message": "Hello"},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "queued"}
    assert len(recorded) == 1
    func, args, _ = recorded[0]
    assert func is send_notification_email
    assert args[0] == "test@example.com"
    assert args[1] == "Hello"


def test_cors_headers_for_allowed_origin():
    """Requests from an allowed origin receive CORS headers."""
    from main import settings

    allowed_origin = settings.allowed_origins[0]
    response = client.get("/health", headers={"Origin": allowed_origin})
    assert response.headers.get("access-control-allow-origin") == allowed_origin


def test_cors_wildcard_not_default():
    """Default ALLOWED_ORIGINS does not include wildcard — wildcard requires explicit opt-in."""
    from main import settings

    assert "*" not in settings.allowed_origins, (
        "Wildcard CORS origin should not be a default — set ALLOWED_ORIGINS explicitly"
    )


def test_cors_disallowed_origin_excluded():
    """Requests from an origin not in allowed_origins must not receive CORS headers."""
    from main import settings
    response = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert response.headers.get("access-control-allow-origin") is None


def test_root_returns_html_when_dist_index_exists(tmp_path, monkeypatch):
    """GET / returns HTMLResponse when dist/index.html exists."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>Hello</body></html>")
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient
    from main import app
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hello" in response.text


def test_notify_invalid_email_returns_422():
    response = client.post("/api/v1/notify", json={"email": "not-an-email", "message": "hi"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_notify_missing_message_returns_422():
    response = client.post("/api/v1/notify", json={"email": "user@example.com"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_notify_empty_message_returns_422():
    """Empty string message is rejected by min_length=1 on NotificationRequest.message."""
    response = client.post("/api/v1/notify", json={"email": "user@example.com", "message": ""})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_notify_whitespace_message_returns_422():
    response = client.post("/api/v1/notify", json={"email": "user@example.com", "message": "   "})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_notify_message_too_long_returns_422():
    """NotificationRequest.message exceeding max_length=1000 returns 422."""
    response = client.post(
        "/api/v1/notify",
        json={"email": "user@example.com", "message": "x" * 1001},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_notify_validation_error_echoes_request_id():
    """validation_exception_handler echoes X-Request-ID for /api/v1/notify 422 responses."""
    response = client.post(
        "/api/v1/notify",
        json={"email": "not-an-email", "message": "hi"},
        headers={"X-Request-ID": "notify-correlation-id"},
    )
    assert response.status_code == 422
    assert response.headers.get("x-request-id") == "notify-correlation-id"


def test_validation_error_echoes_request_id():
    """validation_exception_handler includes X-Request-ID in response header."""
    response = client.post(
        "/api/items",
        json={"price": "not-a-number"},
        headers={"X-Request-ID": "test-correlation-id"},
    )
    assert response.status_code == 422
    assert response.headers.get("x-request-id") == "test-correlation-id"


def test_validation_error_response_includes_generated_request_id():
    """validation_exception_handler echoes the middleware-generated UUID when client sends none."""
    import re
    response = client.post("/api/items", json={"price": "not-a-number"})
    assert response.status_code == 422
    request_id = response.headers.get("x-request-id")
    assert request_id is not None, "X-Request-ID must be present even when client did not send one"
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE,
    )
    assert uuid_pattern.match(request_id), f"Expected UUID4 in X-Request-ID, got: {request_id}"


def test_unhandled_exception_echoes_request_id():
    """generic_exception_handler includes X-Request-ID in response when middleware sets it."""
    from fastapi import FastAPI
    from main import generic_exception_handler, RequestLoggingMiddleware

    isolated = FastAPI()
    isolated.add_exception_handler(Exception, generic_exception_handler)
    isolated.add_middleware(RequestLoggingMiddleware)

    @isolated.get("/_test/raise-error")
    async def raise_error():
        raise RuntimeError("boom")

    error_client = TestClient(isolated, raise_server_exceptions=False)
    response = error_client.get(
        "/_test/raise-error",
        headers={"X-Request-ID": "test-error-id"},
    )
    assert response.status_code == 500
    assert response.headers.get("x-request-id") == "test-error-id"
