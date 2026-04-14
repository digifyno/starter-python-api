"""Tests for middleware behaviors: rate limiting, security headers, and trusted hosts."""
from importlib import reload

from fastapi.testclient import TestClient


def test_security_headers_include_hsts():
    """SecurityHeadersMiddleware sets Strict-Transport-Security (HSTS)."""
    import main as main_module

    client = TestClient(main_module.app)
    response = client.get("/health")
    hsts = response.headers.get("strict-transport-security", "")
    assert "max-age=31536000" in hsts, "HSTS max-age must be 31536000 (1 year)"
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
    limit_responses = [r for r in responses if r.status_code == 429]
    assert len(limit_responses) > 0
    body = limit_responses[0].json()
    assert "detail" in body, f"429 body must use 'detail' key, got: {body}"
    assert "error" not in body, f"429 body must not use legacy 'error' key, got: {body}"


def test_rate_limit_exceeded_on_notify(monkeypatch):
    """slowapi rate limiter returns 429 for /api/v1/notify when limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import main as main_module
    from importlib import reload
    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [
        rl_client.post("/api/v1/notify", json={"email": "test@example.com", "message": "hi"})
        for _ in range(4)
    ]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    assert 202 in status_codes


def test_rate_limit_exceeded_on_create_item(monkeypatch):
    """slowapi rate limiter returns 429 for POST /api/items when limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    from importlib import reload
    import main as main_module
    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [
        rl_client.post("/api/items", json={"name": "Widget", "price": 9.99})
        for _ in range(4)
    ]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    assert 201 in status_codes


def test_rate_limit_exceeded_on_create_todo(monkeypatch):
    """slowapi rate limiter returns 429 for POST /api/todos when limit is exceeded."""
    from importlib import reload
    from unittest.mock import AsyncMock, MagicMock
    from database import TodoItem, get_db

    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import main as main_module
    reload(main_module)

    # Mock the DB so the test runs without a real database
    mock_session = AsyncMock()
    async def fake_refresh(obj):
        obj.id = 1
        obj.done = False
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = fake_refresh

    async def override_get_db():
        yield mock_session

    main_module.app.dependency_overrides[get_db] = override_get_db
    rl_client = TestClient(main_module.app)
    try:
        responses = [
            rl_client.post("/api/todos", json={"title": "Task"})
            for _ in range(4)
        ]
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    assert 201 in status_codes


def test_rate_limit_exceeded_on_get_item(monkeypatch):
    """slowapi rate limiter returns 429 for GET /api/items/{item_id} when limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    from importlib import reload
    import main as main_module
    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [rl_client.get("/api/items/1") for _ in range(4)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "Rate limiter should return 429 when limit is exceeded"
    assert 200 in status_codes, "Rate limiter should allow requests within the limit"


def test_rate_limit_exceeded_on_list_todos(monkeypatch):
    """slowapi rate limiter returns 429 for GET /api/todos when limit is exceeded."""
    from importlib import reload
    from unittest.mock import AsyncMock, MagicMock
    from database import get_db

    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import main as main_module
    reload(main_module)

    mock_session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    mock_session.execute = AsyncMock(return_value=execute_result)

    async def override_get_db():
        yield mock_session

    main_module.app.dependency_overrides[get_db] = override_get_db
    rl_client = TestClient(main_module.app)
    try:
        responses = [rl_client.get("/api/todos") for _ in range(4)]
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "Rate limiter should return 429 when limit is exceeded"
    assert 200 in status_codes, "Rate limiter should allow requests within the limit"


def test_rate_limit_exceeded_on_root(monkeypatch):
    """slowapi rate limiter returns 429 for GET / when limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    from importlib import reload
    import main as main_module
    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [rl_client.get("/") for _ in range(4)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    assert 200 in status_codes


def test_rate_limit_exceeded_on_info(monkeypatch):
    """slowapi rate limiter returns 429 for GET /info when limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    from importlib import reload
    import main as main_module
    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [rl_client.get("/info") for _ in range(4)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    assert 200 in status_codes


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
