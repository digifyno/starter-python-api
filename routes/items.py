from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price: float = Field(ge=0)

    @field_validator('name')
    @classmethod
    def name_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('name must not be blank')
        return v


class ItemResponse(BaseModel):
    item_id: int
    name: str
    price: float


class CreateItemResponse(BaseModel):
    status: str
    item: Item


def create_router(limiter: Limiter, rate_limit: str) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["items"])

    @router.post("/items", response_model=CreateItemResponse, status_code=201)
    @limiter.limit(rate_limit)
    async def create_item(request: Request, item: Item):
        """Create a new item"""
        return {"status": "created", "item": item}

    @router.get("/items/{item_id}", response_model=ItemResponse)
    @limiter.limit(rate_limit)
    async def get_item(request: Request, item_id: int):
        """Get item by ID"""
        return {"item_id": item_id, "name": f"Item {item_id}", "price": 99.99}

    return router
