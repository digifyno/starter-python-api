"""Tests for /api/items endpoints."""
import pytest
from httpx import AsyncClient


async def test_create_item(async_client: AsyncClient):
    response = await async_client.post(
        "/api/items",
        json={"name": "Widget", "description": "A test widget", "price": 9.99},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "created"
    assert data["item"]["name"] == "Widget"
    assert data["item"]["price"] == 9.99


async def test_create_item_missing_price(async_client: AsyncClient):
    response = await async_client.post("/api/items", json={"name": "Widget"})
    assert response.status_code == 422


async def test_create_item_invalid_price(async_client: AsyncClient):
    response = await async_client.post(
        "/api/items", json={"name": "Widget", "price": "not-a-number"}
    )
    assert response.status_code == 422


async def test_get_item(async_client: AsyncClient):
    response = await async_client.get("/api/items/42")
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == 42
    assert "name" in data
    assert "price" in data


async def test_get_item_invalid_id(async_client: AsyncClient):
    response = await async_client.get("/api/items/not-an-int")
    assert response.status_code == 422


async def test_create_item_empty_name_returns_422(async_client: AsyncClient):
    response = await async_client.post("/api/items", json={"name": "", "price": 9.99})
    assert response.status_code == 422


async def test_create_item_whitespace_name_returns_422(async_client: AsyncClient):
    response = await async_client.post("/api/items", json={"name": "   ", "price": 9.99})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data
    # Verify ctx values were serialized (not raw Exception objects)
    for error in data["detail"]:
        if "ctx" in error:
            for v in error["ctx"].values():
                assert isinstance(v, (str, int, float, bool, type(None)))


async def test_create_item_negative_price_returns_422(async_client: AsyncClient):
    response = await async_client.post("/api/items", json={"name": "Widget", "price": -1.00})
    assert response.status_code == 422


async def test_create_item_zero_price_is_valid(async_client: AsyncClient):
    """price=0 is the boundary value for ge=0 and must be accepted."""
    response = await async_client.post("/api/items", json={"name": "Free Item", "price": 0})
    assert response.status_code == 201
    assert response.json()["item"]["price"] == 0
