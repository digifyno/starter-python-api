"""Tests for structured request logging middleware."""
import json
import logging

from fastapi.testclient import TestClient

from main import app


def test_health_check_not_logged(caplog):
    """Health check requests should NOT be logged to reduce noise."""
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        response = client.get("/health")
    assert response.status_code == 200

    # No log record should contain a reference to /health path
    for record in caplog.records:
        msg = record.getMessage()
        try:
            parsed = json.loads(msg)
            assert parsed.get("path") != "/health", (
                "Health check path should be excluded from request logs"
            )
        except (json.JSONDecodeError, ValueError):
            pass


def test_request_logging_logs_json_fields(caplog):
    """Each non-health request should produce a JSON log with method, path, status, duration_ms."""
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        response = client.get("/api/hello")
    assert response.status_code == 200

    log_messages = [r.getMessage() for r in caplog.records]
    json_logs = []
    for msg in log_messages:
        try:
            parsed = json.loads(msg)
            json_logs.append(parsed)
        except (json.JSONDecodeError, ValueError):
            pass

    assert any(
        all(k in log for k in ["request_id", "method", "path", "status", "duration_ms"])
        for log in json_logs
    ), f"No structured log entry with all required fields. Messages: {log_messages}"


def test_request_log_contains_correct_values(caplog):
    """Logged values should match the actual request method, path, and response status."""
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        response = client.get("/api/hello")
    assert response.status_code == 200

    log_messages = [r.getMessage() for r in caplog.records]
    matched = None
    for msg in log_messages:
        try:
            parsed = json.loads(msg)
            if parsed.get("path") == "/api/hello":
                matched = parsed
                break
        except (json.JSONDecodeError, ValueError):
            pass

    assert matched is not None, "No log entry found for /api/hello"
    assert matched["method"] == "GET"
    assert matched["status"] == 200
    assert isinstance(matched["duration_ms"], (int, float))
    assert matched["duration_ms"] >= 0


def test_x_request_id_passthrough():
    """Client-supplied X-Request-ID is echoed back in the response header."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.get("/api/hello", headers={"X-Request-ID": "my-correlation-id"})
    assert response.headers.get("x-request-id") == "my-correlation-id"


def test_x_request_id_generated_when_absent():
    """A UUID X-Request-ID is generated and returned when none is provided."""
    import re
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.get("/api/hello")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
    assert uuid_pattern.match(request_id), f"Expected UUID4, got: {request_id}"


def test_request_id_in_log_matches_client_header(caplog):
    """Client-supplied X-Request-ID appears in the structured log's request_id field."""
    client = TestClient(app)
    correlation_id = "test-log-correlation-abc123"
    with caplog.at_level(logging.INFO):
        response = client.get("/api/hello", headers={"X-Request-ID": correlation_id})
    assert response.status_code == 200

    log_messages = [r.getMessage() for r in caplog.records]
    matched = None
    for msg in log_messages:
        try:
            parsed = json.loads(msg)
            if parsed.get("path") == "/api/hello":
                matched = parsed
                break
        except (json.JSONDecodeError, ValueError):
            pass

    assert matched is not None, "No structured log entry found for /api/hello"
    assert matched["request_id"] == correlation_id, (
        f"Log request_id should match client-supplied X-Request-ID, got: {matched['request_id']}"
    )


def test_no_query_params_in_log(caplog):
    """Query parameters (PII risk) should NOT appear in the default log entry."""
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        # Pass a query param that must not appear in the structured log
        response = client.get("/api/hello?secret=topsecret")

    log_messages = [r.getMessage() for r in caplog.records]
    for msg in log_messages:
        try:
            parsed = json.loads(msg)
            # The path field must not include query params
            if "path" in parsed:
                assert "topsecret" not in parsed["path"], (
                    "Query params must not appear in logged path"
                )
                assert "?" not in parsed["path"], (
                    "Query string must not appear in the logged path field"
                )
        except (json.JSONDecodeError, ValueError):
            pass


def test_health_response_has_no_request_id_header():
    """RequestLoggingMiddleware skips /health — response must not carry X-Request-ID."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-request-id") is None, (
        "/health must not emit X-Request-ID — middleware bypass must skip header injection"
    )


def test_notification_log_omits_message_body(caplog):
    """Background task log must not contain message content (PII protection)."""
    import logging
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    sensitive_message = "secret-payload-12345"
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/notify",
            json={"email": "test@example.com", "message": sensitive_message},
        )
    assert response.status_code == 202

    for record in caplog.records:
        assert sensitive_message not in record.getMessage(), (
            "Notification message body must not appear in logs"
        )

    # Positive: verify the notification_sent event IS logged
    notification_logs = []
    for record in caplog.records:
        try:
            parsed = json.loads(record.getMessage())
            if parsed.get("event") == "notification_sent":
                notification_logs.append(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
    assert len(notification_logs) == 1, "Expected exactly one notification_sent log entry"
    assert notification_logs[0]["email"] == "test@example.com"
