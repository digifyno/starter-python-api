import os

from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it in .env or as an environment variable before starting the server. "
            "Example: DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname"
        )
    async with AsyncSessionLocal() as session:
        yield session
