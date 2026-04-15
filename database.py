import os

from fastapi import HTTPException
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Set DATABASE_URL in .env or environment.
# Format: postgresql+asyncpg://user:password@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    engine = None
    AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


# Example ORM model — replace or extend for your domain.
class TodoItem(Base):
    __tablename__ = "todo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(default=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session.

    Usage::

        @app.get("/api/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured — set DATABASE_URL environment variable",
        )
    async with AsyncSessionLocal() as session:
        yield session
