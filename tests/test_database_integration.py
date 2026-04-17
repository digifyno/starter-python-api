"""SQLite integration tests for /api/todos routes.

These tests exercise the real SQLAlchemy ORM query, commit, and refresh
lifecycle against an in-memory SQLite database — no mocks, no get_db overrides.
"""
import pytest
from httpx import AsyncClient, ASGITransport

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_client(monkeypatch):
    """AsyncClient backed by a real in-memory SQLite database."""
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    from importlib import reload
    import database as db_module
    import main as main_module

    reload(db_module)
    reload(main_module)

    async with db_module.engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test") as ac:
        yield ac

    async with db_module.engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.drop_all)


async def test_list_todos_empty_on_fresh_db(db_client):
    response = await db_client.get("/api/todos")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_todo_persists(db_client):
    post = await db_client.post("/api/todos", json={"title": "Buy milk"})
    assert post.status_code == 201

    get = await db_client.get("/api/todos")
    assert get.status_code == 200
    items = get.json()
    assert len(items) == 1
    assert items[0]["title"] == "Buy milk"


async def test_create_multiple_todos(db_client):
    await db_client.post("/api/todos", json={"title": "First"})
    await db_client.post("/api/todos", json={"title": "Second"})

    response = await db_client.get("/api/todos")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    titles = {item["title"] for item in items}
    assert titles == {"First", "Second"}
    for item in items:
        assert "id" in item
        assert "title" in item
        assert "done" in item


async def test_create_todo_done_defaults_to_false(db_client):
    response = await db_client.post("/api/todos", json={"title": "Check default"})
    assert response.status_code == 201
    assert response.json()["done"] is False


async def test_todo_title_persisted_exactly(db_client):
    long_title = "A" * 200
    post = await db_client.post("/api/todos", json={"title": long_title})
    assert post.status_code == 201

    items = (await db_client.get("/api/todos")).json()
    assert len(items) == 1
    assert items[0]["title"] == long_title
