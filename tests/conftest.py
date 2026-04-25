"""Configure pytest to include the project root in the Python path."""
import sys
import os

# Set DATABASE_URL before importing any project modules so database.py
# creates an engine instead of leaving engine=None. Tests that don't use
# the database override get_db with a mock, so the SQLite URL is harmless.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

# Add the project root directory to sys.path so `from main import app` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture(autouse=True)
def evict_route_modules():
    """Evict route modules before each test so reload(main) re-binds @limiter.limit()."""
    for mod in ("routes.items", "routes.todos", "routes.notify"):
        sys.modules.pop(mod, None)
    yield


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
