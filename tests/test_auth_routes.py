"""Tests for auth API routes: register, login, and /api/me."""

import pytest
from fastapi.testclient import TestClient

import main as main_module
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_users():
    """Reset in-memory user store before each test to prevent cross-test pollution."""
    main_module._users.clear()
    yield
    main_module._users.clear()


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

def test_register_success():
    response = client.post("/api/auth/register", json={"username": "alice", "password": "strongpass"})
    assert response.status_code == 201
    assert response.json() == {"status": "registered"}


def test_register_creates_user():
    client.post("/api/auth/register", json={"username": "alice", "password": "strongpass"})
    assert "alice" in main_module._users


def test_register_duplicate_username_returns_409():
    client.post("/api/auth/register", json={"username": "alice", "password": "strongpass"})
    response = client.post("/api/auth/register", json={"username": "alice", "password": "anotherpass"})
    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]


def test_register_username_too_short_returns_422():
    response = client.post("/api/auth/register", json={"username": "ab", "password": "strongpass"})
    assert response.status_code == 422


def test_register_password_too_short_returns_422():
    response = client.post("/api/auth/register", json={"username": "alice", "password": "short"})
    assert response.status_code == 422


def test_register_missing_fields_returns_422():
    response = client.post("/api/auth/register", json={"username": "alice"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

def test_login_success_returns_token():
    client.post("/api/auth/register", json={"username": "alice", "password": "strongpass"})
    response = client.post("/api/auth/login", json={"username": "alice", "password": "strongpass"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


def test_login_wrong_password_returns_401():
    client.post("/api/auth/register", json={"username": "alice", "password": "strongpass"})
    response = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_unknown_username_returns_401():
    response = client.post("/api/auth/login", json={"username": "ghost", "password": "doesntmatter"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------

def _get_token(username: str = "alice", password: str = "strongpass") -> str:
    client.post("/api/auth/register", json={"username": username, "password": password})
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def test_me_with_valid_token_returns_username():
    token = _get_token()
    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"username": "alice"}


def test_me_without_token_returns_403():
    response = client.get("/api/me")
    assert response.status_code == 403


def test_me_with_invalid_token_returns_401():
    response = client.get("/api/me", headers={"Authorization": "Bearer not.a.valid.token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_me_with_expired_token_returns_401():
    from datetime import timedelta
    from auth import create_access_token
    from main import settings

    expired_token = create_access_token(
        {"sub": "alice"}, settings.secret_key, expires_in=timedelta(seconds=-1)
    )
    response = client.get("/api/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"
