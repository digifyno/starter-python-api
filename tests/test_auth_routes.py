"""Tests for auth API routes: register, login, and /api/me."""

import pytest
from httpx import AsyncClient, ASGITransport

import main as main_module


@pytest.fixture(autouse=True)
def clear_users():
    """Reset the in-memory user store before each test."""
    main_module._users.clear()
    yield
    main_module._users.clear()


@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

async def test_register_success(async_client):
    response = await async_client.post(
        "/api/auth/register", json={"username": "alice", "password": "securepass123"}
    )
    assert response.status_code == 201
    assert response.json() == {"status": "registered"}


async def test_register_stores_hashed_password(async_client):
    await async_client.post(
        "/api/auth/register", json={"username": "bob", "password": "mypassword1"}
    )
    assert "bob" in main_module._users
    assert main_module._users["bob"] != "mypassword1"
    assert main_module._users["bob"].startswith("$2b$")


async def test_register_duplicate_username_returns_409(async_client):
    payload = {"username": "alice", "password": "securepass123"}
    await async_client.post("/api/auth/register", json=payload)
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Username already taken"


async def test_register_short_username_returns_422(async_client):
    response = await async_client.post(
        "/api/auth/register", json={"username": "ab", "password": "securepass123"}
    )
    assert response.status_code == 422


async def test_register_short_password_returns_422(async_client):
    response = await async_client.post(
        "/api/auth/register", json={"username": "alice", "password": "short"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

async def test_login_success(async_client):
    await async_client.post(
        "/api/auth/register", json={"username": "alice", "password": "securepass123"}
    )
    response = await async_client.post(
        "/api/auth/login", json={"username": "alice", "password": "securepass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


async def test_login_wrong_password_returns_401(async_client):
    await async_client.post(
        "/api/auth/register", json={"username": "alice", "password": "securepass123"}
    )
    response = await async_client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_unknown_user_returns_401(async_client):
    response = await async_client.post(
        "/api/auth/login", json={"username": "nobody", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------

async def test_me_with_valid_token(async_client):
    await async_client.post(
        "/api/auth/register", json={"username": "alice", "password": "securepass123"}
    )
    login_resp = await async_client.post(
        "/api/auth/login", json={"username": "alice", "password": "securepass123"}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.get(
        "/api/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"username": "alice"}


async def test_me_without_token_returns_403(async_client):
    response = await async_client.get("/api/me")
    assert response.status_code == 403


async def test_me_with_invalid_token_returns_401(async_client):
    response = await async_client.get(
        "/api/me", headers={"Authorization": "Bearer not.a.valid.token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


async def test_me_with_expired_token_returns_401(async_client):
    from datetime import timedelta
    from auth import create_access_token

    token = create_access_token(
        {"sub": "alice"}, main_module.settings.secret_key, expires_in=timedelta(seconds=-1)
    )
    response = await async_client.get(
        "/api/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"
