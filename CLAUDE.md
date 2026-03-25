# Python FastAPI Starter - Claude Development Guide

## Stack

- **Python 3.12+**
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation

## Development Commands

```bash
# First-time setup
cp .env.example .env        # copy template, then edit .env with your values
```

```bash
# Using uv (recommended)
uv sync                     # create .venv and install all deps
uv sync --group dev         # also install dev deps
uv run python main.py       # run dev server without activating venv
uv run pytest tests/        # run tests

# Or with traditional pip/venv:
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt          # production deps
pip install -r requirements-dev.txt      # dev + test deps
```

```bash
# Run development server (auto-reload enabled)
python main.py
# Or:
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/

# Freeze dependencies
pip freeze > requirements.txt

# Audit for known vulnerabilities
uv run pip-audit
# or: pip-audit -r requirements.txt
```

## Project Structure

```
main.py              # FastAPI app entry point — registers routers, middleware, lifespan handler
routes/              # APIRouter modules (register in main.py via app.include_router)
settings.py          # pydantic-settings Settings class (SECRET_KEY, ALLOWED_ORIGINS, DEBUG, RATE_LIMIT, ALLOWED_HOSTS)
database.py          # SQLAlchemy async engine, models, get_db dependency
requirements.txt     # Production dependencies
requirements-dev.txt # Dev/test dependencies
tests/               # Test files (conftest, test_main, test_database, test_logging, test_settings, test_middleware)
dist/                # Static files (optional)
.env.example         # Environment variable template
pytest.ini           # Pytest configuration (asyncio_mode = auto)
venv.py              # Workaround shim for missing python3.12-venv system package (only needed if system lacks python3.12-venv)
```

## Key Patterns

### Define Routes

Use `APIRouter` to group related routes and register them in `main.py`. This keeps route logic modular as the codebase grows.

```python
# routes/items.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["items"])

@router.get("/items")
async def get_items():
    return {"items": []}

@router.post("/items")
async def create_item(item: Item):
    return {"created": item}

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    return {"id": item_id}
```

Register in `main.py`:

```python
from routes.items import router as items_router
app.include_router(items_router)
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

### Alembic migrations (production)

```bash
pip install alembic
alembic init migrations
```

In `migrations/env.py`, import your `Base` and set the metadata:

```python
from database import Base
target_metadata = Base.metadata
```

In `alembic.ini`, set `sqlalchemy.url` or override from env:

```python
# migrations/env.py — override url from environment
import os
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "").replace("+asyncpg", "+psycopg2"))
```

Note: Alembic uses synchronous psycopg2 for migrations even if your app uses asyncpg. Add `psycopg2-binary` to `requirements.txt` when using Alembic.

```bash
alembic revision --autogenerate -m "initial"
alembic upgrade head
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

## Middleware Stack

Middleware is registered in `main.py` and executes in **reverse registration order** (last registered = outermost, processes requests first):

| Order (request) | Middleware | Notes |
|---|---|---|
| 1st | RequestLoggingMiddleware | Structured JSON logs with `request_id`; skips `/health` |
| 2nd | SecurityHeadersMiddleware | Sets 7 security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 0`, `Referrer-Policy`, CSP, `Permissions-Policy`, HSTS — see table below |
| 3rd | TrustedHostMiddleware | **Production only** (skipped when `DEBUG=true`); validates `Host` header |
| 4th | GZipMiddleware | Compresses responses ≥ 1000 bytes |
| 5th | CORSMiddleware | Reads `ALLOWED_ORIGINS` env var (innermost) |
| Per-route | slowapi rate limiter | Applied via `@limiter.limit()` decorator; default: 100/minute |

### Security Headers (SecurityHeadersMiddleware)

All responses include these headers (set in `main.py`, `SecurityHeadersMiddleware`):

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `0` (disabled — deprecated and harmful in old browsers) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none';` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |

**Production customization notes:**

- **CSP `style-src 'unsafe-inline'`**: Required for inline styles (e.g., CSS-in-JS, some component libraries). If your app uses an external stylesheet CDN, add `style-src 'self' 'unsafe-inline' https://cdn.example.com`. To tighten further, replace `'unsafe-inline'` with a nonce or hash.
- **CSP `img-src 'self' data:`**: `data:` allows base64-encoded images. Add external image hosts as needed (e.g., `img-src 'self' data: https://images.example.com`).
- **HSTS**: Also configure at the nginx level (`add_header Strict-Transport-Security`) so the header is sent on the initial HTTP→HTTPS redirect before the app processes the request.
- **`frame-ancestors 'none'`**: Redundant with `X-Frame-Options: DENY` but required for CSP-aware browsers. Both are set for maximum compatibility.

To customize these headers, edit `SecurityHeadersMiddleware.dispatch()` in `main.py`.

### Rate Limiting Setup

Wire `slowapi` into the app once in `main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Then apply per-route overrides with `@limiter.limit()`:

```python
@router.get("/items")
@limiter.limit("10/minute")
async def get_items(request: Request):  # Request is required by slowapi even if unused
    return {"items": []}
```

> **Note:** slowapi requires `request: Request` as a parameter in every rate-limited route handler, even if the handler doesn't use it directly.

**Configuring rate limits:**

Set `RATE_LIMIT=60/minute` (or any [limits string](https://limits.readthedocs.io/en/stable/quickstart.html)) in `.env` to change the default. This value is wired to `settings.rate_limit` and passed to `Limiter(default_limits=[settings.rate_limit])`.

> **Multi-process deployments (Gunicorn)**: The default in-memory storage is **per-process**. With `-w 4`, each worker tracks its own counter — a client sees 4× the configured limit. For accurate rate limiting in production, either:
> 1. Run with a single worker (`-w 1`) — loses concurrency.
> 2. Use a Redis-backed storage backend:
>
> ```bash
> pip install limits[redis]
> ```
>
> ```python
> from limits.storage import RedisStorage
> limiter = Limiter(
>     key_func=get_remote_address,
>     default_limits=[settings.rate_limit],
>     storage_uri="redis://localhost:6379",
> )
> ```
>
> Set `REDIS_URL` in `.env` and pass it to `storage_uri`. Without Redis, rate limiting in multi-worker deployments is not enforceable.

**Configuring trusted hosts (production):**

Set `ALLOWED_HOSTS` in `.env` to a JSON array of permitted hostnames:

```
ALLOWED_HOSTS=["myapp.com","www.myapp.com"]
```

When `DEBUG=true`, `TrustedHostMiddleware` is disabled and all hosts are accepted. In production (`DEBUG=false`), requests with an unrecognized `Host` header receive a `400 Bad Request` response. If `ALLOWED_HOSTS` is not set, defaults to `["*"]` (all hosts accepted — restrict this in production).

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

> **Important**: `PyJWT` and `bcrypt` are in `requirements-dev.txt` as examples.
> These are example implementations — to use them in production, add `PyJWT` and `bcrypt`
> to `requirements.txt` and remove them from `requirements-dev.txt`.

```python
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

def hash_password(password: str) -> str:
    # bcrypt work factor: target ~250ms on your production hardware
    # Default 12 rounds is reasonable; increase to 13-14 for stricter security
    # Benchmark: python -c "import bcrypt, time; t=time.time(); bcrypt.hashpw(b'test', bcrypt.gensalt(12)); print(time.time()-t)"
    # Adjust rounds so hashing takes 100-300ms on your production server.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_access_token(data: dict, secret_key: str, expires_in: timedelta = timedelta(hours=1)) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(payload, secret_key, algorithm="HS256")

def decode_access_token(token: str, secret_key: str) -> dict:
    # PyJWT automatically validates 'exp' — raises jwt.ExpiredSignatureError if expired
    return jwt.decode(token, secret_key, algorithms=["HS256"])
```

Handle token errors in route handlers — catch `ExpiredSignatureError` separately for a clear `401` message:

```python
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

def get_current_user(token: str):
    try:
        payload = decode_access_token(token, settings.secret_key)
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Testing

Dependencies (`pytest` and `httpx`) are already in `requirements-dev.txt`.

### Async tests (primary pattern)

The project uses `asyncio_mode = auto` in `pytest.ini`, so **no `@pytest.mark.asyncio` decorator is needed** — any `async def` test function runs automatically under asyncio.

Use `AsyncClient` with `ASGITransport` to test the full ASGI stack (middleware, lifespan, async DB sessions) without starting a real server:

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

```python
# tests/test_main.py
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
```

**Testing rate limits**: slowapi stores hit counts in memory on the `limiter` instance. Tests that exhaust the limit leave state behind and will cause subsequent tests to see stale counts. Use `monkeypatch` + module reload to get a fresh limiter with a low limit, avoiding cross-test pollution:

```python
# tests/test_middleware.py
from importlib import reload
from fastapi.testclient import TestClient

def test_rate_limit_exceeded(monkeypatch):
    """slowapi rate limiter returns 429 when request limit is exceeded."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import main as main_module

    reload(main_module)
    rl_client = TestClient(main_module.app)
    responses = [rl_client.get("/api/hello") for _ in range(4)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "Rate limiter should return 429 when limit is exceeded"
    assert 200 in status_codes, "Rate limiter should allow requests within the limit"
```

> **Why reload?** The `limiter` object is module-level state in `main.py`. Without a reload, hit counts from previous tests accumulate and can cause unrelated tests to receive unexpected 429 responses. The `monkeypatch` + `reload` pattern creates a fresh module with a clean limiter and a low `RATE_LIMIT` so the test doesn't need to fire 100+ requests.

### Sync alternative (quick checks)

For simple smoke tests that don't involve async DB sessions or middleware ordering, the synchronous `TestClient` is a shorter option:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
```

> Prefer `AsyncClient` for tests that touch middleware, database sessions, or rate limiting — these exercise the real async code paths. Use `TestClient` only for quick, isolated endpoint checks.
## Production Deployment

### Gunicorn
```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

> **Rate limiting**: The default in-memory limiter is not shared across workers. See [Rate Limiting Setup](#rate-limiting-setup) for multi-worker configuration.

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

`SECRET_KEY` must be at least 32 characters **and** have sufficient randomness (Shannon entropy ≥ 3.0 bits/char). Weak keys (e.g. all-same character, short repeating patterns) are rejected at startup with `ValidationError: entropy too low`.

Generate a strong key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set it in `.env` or as an environment variable before starting the server.

