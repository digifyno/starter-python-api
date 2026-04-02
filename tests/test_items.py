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
