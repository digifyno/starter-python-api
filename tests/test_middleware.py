"""Tests for middleware behaviors: rate limiting, security headers, and trusted hosts."""
from importlib import reload

from fastapi.testclient import TestClient


def test_security_headers_include_hsts():
    """SecurityHeadersMiddleware sets Strict-Transport-Security (HSTS)."""
    import main as main_module

    client = TestClient(main_module.app)
    response = client.get("/health")
    hsts = response.headers.get("strict-transport-security", "")
    assert "max-age=" in hsts, "HSTS header must include max-age directive"
    assert "includeSubDomains" in hsts, "HSTS header must include includeSubDomains"


def test_rate_limit_exceeded(monkeypatch):
    """slowapi rate limiter returns 429 when request limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import main as main_module

    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [rl_client.get("/api/hello") for _ in range(4)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "Rate limiter should return 429 when limit is exceeded"
    assert 200 in status_codes, "Rate limiter should allow requests within the limit"


def test_trusted_host_rejects_unknown_host(monkeypatch):
    """TrustedHostMiddleware returns 400 for requests with an unknown Host header."""
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("ALLOWED_HOSTS", '["myapp.com"]')
    import main as main_module

    reload(main_module)
    th_client = TestClient(main_module.app, raise_server_exceptions=False)
    response = th_client.get("/", headers={"Host": "evil.com"})
    assert response.status_code == 400


def test_trusted_host_allows_known_host(monkeypatch):
    """TrustedHostMiddleware allows requests with a valid Host header."""
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("ALLOWED_HOSTS", '["myapp.com"]')
    import main as main_module

    reload(main_module)
    th_client = TestClient(main_module.app, base_url="http://myapp.com")
    response = th_client.get("/health")
    assert response.status_code == 200


def test_trusted_host_disabled_in_debug_mode(monkeypatch):
    """TrustedHostMiddleware is not registered when DEBUG=true — any host is accepted."""
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_HOSTS", '["myapp.com"]')
    import main as main_module

    reload(main_module)
    debug_client = TestClient(main_module.app)
    # Even a disallowed host must be accepted in debug mode
    response = debug_client.get("/health", headers={"Host": "evil.com"})
    assert response.status_code == 200
