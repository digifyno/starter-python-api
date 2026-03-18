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
        all(k in log for k in ["method", "path", "status", "duration_ms"])
        for log in json_logs
    ), f"No structured log entry found with required fields. Messages: {log_messages}"


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
