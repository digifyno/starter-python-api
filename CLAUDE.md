# Python FastAPI Starter - Claude Development Guide

## Stack

- **Python 3.12+**
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation

## Development Commands

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt          # production deps
pip install -r requirements-dev.txt      # dev + test deps

# Run development server (auto-reload enabled)
python main.py
# Or:
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/

# Freeze dependencies
pip freeze > requirements.txt
```

## Project Structure

```
main.py              # FastAPI app
requirements.txt     # Dependencies
tests/              # Test files
dist/               # Static files (optional)
```

## Key Patterns

### Define Routes
```python
@app.get("/api/items")
async def get_items():
    return {"items": []}

@app.post("/api/items")
async def create_item(item: Item):
    return {"created": item}

@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    return {"id": item_id}
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str
    email: str
    age: int = Field(gt=0, le=120)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30
            }
        }
```

### Async Operations
```python
import httpx

@app.get("/api/external")
async def fetch_external():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

### Dependency Injection
```python
from fastapi import Depends

def get_current_user(token: str):
    # Verify token, return user
    return {"user_id": 1}

@app.get("/api/me")
async def read_users_me(user = Depends(get_current_user)):
    return user
```

### Error Handling
```python
from fastapi import HTTPException

@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    if item_id not in database:
        raise HTTPException(status_code=404, detail="Item not found")
    return database[item_id]
```

### Background Tasks
```python
# Use BackgroundTasks for fire-and-forget work (email hooks, audit logs).
# For retries, persistence, or distributed execution, use Celery or ARQ.
from fastapi import BackgroundTasks

def background_job(param: str):
    # Can also be async def
    ...

@app.post("/api/v1/notify", status_code=202)
async def notify(bg: BackgroundTasks):
    bg.add_task(background_job, "value")
    return {"status": "queued"}
```

## Environment Variables

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
```

## Database Integration

### SQLAlchemy (PostgreSQL) — async

> **Important:** Use SQLAlchemy 2.x async with FastAPI — the synchronous `create_engine` API
> blocks the event loop and will deadlock under concurrent requests.

```bash
pip install sqlalchemy>=2.0 asyncpg
```

```python
# database.py
import os

from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

Wire the engine into FastAPI's lifespan for clean startup/shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables when DATABASE_URL is configured.
    # For production, use Alembic migrations instead of create_all.
    if os.getenv("DATABASE_URL"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()  # release connection pool on shutdown
```

Use `Depends(get_db)` in route handlers:

```python
from sqlalchemy import select

@app.get("/api/items")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

### MongoDB (Motor)
```bash
pip install motor
```

```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.mydatabase
```

## CORS (for frontend)

CORS origins are configured via the `ALLOWED_ORIGINS` environment variable (see `.env.example`).
Do not hardcode origins — use `settings.allowed_origins` instead:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # set via ALLOWED_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
```

In `.env` or environment:
```
# Development
ALLOWED_ORIGINS=["http://localhost:3000"]

# Production (comma-separated JSON array)
ALLOWED_ORIGINS=["https://myapp.com","https://www.myapp.com"]
```

## Authentication

### JWT Tokens
```bash
pip install PyJWT bcrypt
```

```python
import jwt
import bcrypt
from jwt.exceptions import InvalidTokenError

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_access_token(data: dict, secret_key: str) -> str:
    return jwt.encode(data, secret_key, algorithm="HS256")

def decode_access_token(token: str, secret_key: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=["HS256"])
```

## Testing

```bash
pip install pytest httpx
```

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
```

## Production Deployment

### Gunicorn
```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### systemd Service
```ini
[Unit]
Description=FastAPI App
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/myapp
ExecStart=/var/www/myapp/venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Interactive Docs

- Swagger UI: http://localhost:8000/docs (DEBUG=true only)
- ReDoc: http://localhost:8000/redoc (DEBUG=true only)
- OpenAPI JSON: http://localhost:8000/openapi.json (DEBUG=true only)

## Logging

All request logs are structured JSON via the `RequestLoggingMiddleware`. Every log entry includes a `request_id` for correlation:

```json
{"request_id": "550e8400-e29b-41d4-a716-446655440000", "method": "GET", "path": "/api/hello", "status": 200, "duration_ms": 12.5}
```

### Correlation ID pattern

- If the client sends an `X-Request-ID` header, that value is used (pass-through for upstream correlation).
- Otherwise a UUID4 is generated for the request.
- The ID is stored on `request.state.request_id` so route handlers and exception handlers can access it.
- The ID is echoed back in the `X-Request-ID` response header.
- Exception handlers (`validation_exception_handler`, `generic_exception_handler`) include the `request_id` in the `X-Request-ID` response header and in the log message.

```python
# Access in route handlers or dependencies:
@app.get("/api/example")
async def example(request: Request):
    request_id = getattr(request.state, "request_id", None)
    ...
```

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)

## JWT Secret Key

`SECRET_KEY` must be at least 32 characters. Shorter values cause a `ValidationError` at startup with an actionable message.

Generate a strong key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set it in `.env` or as an environment variable before starting the server.

