"""Tests for async database routes (/api/todos).

These tests override the get_db dependency with a mock session so they run
without a real database.  To test against a real database, set DATABASE_URL in
your environment and remove the dependency override.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from database import TodoItem, get_db
from main import app


def _make_mock_db(rows=None):
    """Return an AsyncMock session whose execute() yields *rows*."""
    session = AsyncMock()

    scalars = MagicMock()
    scalars.all.return_value = rows or []

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars

    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture()
def client():
    """Test client with mocked get_db dependency."""

    mock_session = _make_mock_db()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_list_todos_returns_empty_list(client):
    """GET /api/todos returns an empty list when no todos exist."""
    response = client.get("/api/todos")
    assert response.status_code == 200
    assert response.json() == []


def test_list_todos_returns_items(client):
    """GET /api/todos returns serialized TodoItem rows."""
    item = TodoItem(id=1, title="Write tests", done=False)
    mock_session = _make_mock_db(rows=[item])

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/todos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Write tests"
    assert data[0]["done"] is False
    assert data[0]["id"] == 1


def test_create_todo_returns_201(client):
    """POST /api/todos creates a new item and returns 201."""
    # refresh() populates the returned item with id from the DB
    async def fake_refresh(obj):
        obj.id = 42
        obj.done = False

    mock_session = _make_mock_db()
    mock_session.refresh = fake_refresh  # sync-compatible side effect

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    response = client.post("/api/todos", json={"title": "Buy milk"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Buy milk"
    assert data["id"] == 42
    assert data["done"] is False
    mock_session.add.assert_called_once()  # verify item was persisted
    mock_session.commit.assert_awaited_once()  # verify commit was awaited


def test_list_todos_returns_multiple_items(client):
    """GET /api/todos returns all TodoItem rows when multiple exist."""
    items = [
        TodoItem(id=1, title="First task", done=False),
        TodoItem(id=2, title="Second task", done=True),
    ]
    mock_session = _make_mock_db(rows=items)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/todos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["title"] == "First task"
    assert data[0]["done"] is False
    assert data[1]["id"] == 2
    assert data[1]["title"] == "Second task"
    assert data[1]["done"] is True


def test_create_todo_requires_title(client):
    """POST /api/todos without a title returns 422 Unprocessable Entity."""
    response = client.post("/api/todos", json={})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_create_todo_empty_title_returns_422(client):
    """POST /api/todos with an empty title returns 422 Unprocessable Entity."""
    response = client.post("/api/todos", json={"title": ""})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


def test_create_todo_whitespace_title_returns_422(client):
    response = client.post("/api/todos", json={"title": "   "})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data
    for error in data["detail"]:
        if "ctx" in error:
            for v in error["ctx"].values():
                assert isinstance(v, (str, int, float, bool, type(None)))


def test_create_todo_title_too_long_returns_422(client):
    """POST /api/todos with a title exceeding 200 characters returns 422."""
    response = client.post("/api/todos", json={"title": "x" * 201})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data
