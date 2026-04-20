from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import TodoItem, get_db
from main import limiter, settings

router = APIRouter(prefix="/api", tags=["todos"])


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator('title')
    @classmethod
    def title_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('title must not be blank')
        return v


class TodoOut(BaseModel):
    id: int
    title: str
    done: bool

    model_config = {"from_attributes": True}


# EXAMPLE: Async SQLAlchemy with dependency injection.
# These routes demonstrate the async database pattern — adapt for your domain.
@router.get("/todos", response_model=list[TodoOut])
@limiter.limit(settings.rate_limit)
async def list_todos(request: Request, db: AsyncSession = Depends(get_db)):
    """List all todo items. Demonstrates async SQLAlchemy query via Depends(get_db)."""
    result = await db.execute(select(TodoItem))
    return result.scalars().all()


@router.post("/todos", response_model=TodoOut, status_code=201)
@limiter.limit(settings.rate_limit)
async def create_todo(request: Request, todo: TodoCreate, db: AsyncSession = Depends(get_db)):
    """Create a todo item. Demonstrates async SQLAlchemy write via Depends(get_db)."""
    item = TodoItem(title=todo.title)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
