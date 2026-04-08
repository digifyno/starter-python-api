import json
import logging
import math
import os
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from database import Base, TodoItem, engine, get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "FastAPI Starter"
    debug: bool = False
    secret_key: str = "change-me-in-production-not-for-real-use"
    allowed_origins: list[str] = ["http://localhost:3000"]  # Override via ALLOWED_ORIGINS env var
    allowed_hosts: list[str] = ["*"]  # Override in production: ALLOWED_HOSTS=["yourdomain.com"]
    rate_limit: str = "100/minute"  # Override via RATE_LIMIT env var

    @field_validator('secret_key')
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                'SECRET_KEY must be at least 32 characters. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        counts = Counter(v)
        entropy = -sum((c / len(v)) * math.log2(c / len(v)) for c in counts.values())
        if entropy < 3.0:
            raise ValueError(
                'SECRET_KEY entropy too low — use a randomly generated key. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v


settings = Settings()


def get_settings() -> Settings:
    """Return the shared Settings instance. Use with FastAPI Depends() for DI."""
    return settings


STARTUP_TIME = time.time()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables when DATABASE_URL is configured.
    # For production, use Alembic migrations instead of create_all.
    if os.getenv("DATABASE_URL"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if not settings.debug and settings.allowed_hosts == ["*"]:
        logger.warning(
            "SECURITY WARNING: ALLOWED_HOSTS is set to '*' in production mode. "
            "Set the ALLOWED_HOSTS environment variable to restrict accepted Host headers. "
            'Example: ALLOWED_HOSTS=["myapp.com","www.myapp.com"]'
        )
    if not settings.debug and settings.secret_key == "change-me-in-production-not-for-real-use":
        logger.warning(
            "SECURITY WARNING: SECRET_KEY is set to the publicly known default value. "
            "This key is not secret. Set a randomly generated key: "
            'python -c \'import secrets; print(secrets.token_hex(32))\''
        )
    logger.info("Starting up")
    yield
    await engine.dispose()
    logger.info("Shutting down")


app = FastAPI(
    title="Python FastAPI Starter",
    description="A minimal FastAPI backend starter template",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    # Disable interactive docs in production to avoid schema exposure
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. CORS — reads from settings.allowed_origins (set via ALLOWED_ORIGINS env var, not wildcard!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# 2. GZip compression for responses > 1000 bytes
app.add_middleware(GZipMiddleware, minimum_size=1000)

# In production, set ALLOWED_HOSTS=["yourdomain.com"] to restrict host header spoofing
# 3. Trusted host validation (configure via settings in prod)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )


# 4. Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Disable legacy header (deprecated by browsers)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        # HSTS: enforce HTTPS for 1 year. Also configure at nginx level for
        # preloading and to protect the initial HTTP request before redirect.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# 5. Request logging middleware — logs method, path, status, duration_ms as JSON.
#    /health is excluded to reduce noise. No query params or body (no PII).
#    Generates or echoes X-Request-ID header for log correlation across services.
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            json.dumps({
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            })
        )
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)

# Serve static files from dist/ directory
if os.path.exists("dist"):
    app.mount("/static", StaticFiles(directory="dist"), name="static")


# Exception handlers
def _serializable_errors(errors: list) -> list:
    """Convert Pydantic v2 validation errors to JSON-serializable dicts.

    field_validator raises store the original exception in ctx['error'], which
    is not JSON serializable. Convert any non-primitive ctx values to strings.
    """
    result = []
    for err in errors:
        err = dict(err)
        if 'ctx' in err:
            err['ctx'] = {
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in err['ctx'].items()
            }
        result.append(err)
    return result


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "detail": _serializable_errors(exc.errors()),
            "body": exc.body,
        },
        headers={"X-Request-ID": request_id} if request_id else {},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception for %s %s (request_id=%s)",
        request.method,
        request.url.path,
        request_id,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={"X-Request-ID": request_id} if request_id else {},
    )


# Models
class Item(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    price: float = Field(ge=0)

    @field_validator('name')
    @classmethod
    def name_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('name must not be blank')
        return v


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int


class HelloResponse(BaseModel):
    message: str


class ItemResponse(BaseModel):
    item_id: int
    name: str
    price: float


class CreateItemResponse(BaseModel):
    status: str
    item: Item


class InfoResponse(BaseModel):
    app_name: str
    debug: bool


class NotificationRequest(BaseModel):
    email: EmailStr
    message: str = Field(min_length=1)

    @field_validator('message')
    @classmethod
    def message_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('message must not be blank')
        return v


# Background task function — simulates a fire-and-forget email notification.
# async def can also be used here for non-blocking I/O in the background.
def send_notification_email(email: str, message: str) -> None:
    time.sleep(0.1)  # Simulate work (e.g., SMTP call)
    logger.info(json.dumps({"event": "notification_sent", "email": email}))


# Routes
@app.get("/")
async def root():
    """Serve the main HTML page if dist/index.html exists, otherwise return API info"""
    if os.path.exists("dist/index.html"):
        with open("dist/index.html", "r") as f:
            return HTMLResponse(content=f.read())

    return {
        "message": "FastAPI Backend",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health_check():
    """Health check endpoint with uptime"""
    return {
        "status": "healthy",
        "uptime_seconds": int(time.time() - STARTUP_TIME),
    }


@app.get("/info", tags=["info"], response_model=InfoResponse)
async def info(s: Settings = Depends(get_settings)):
    """Application info — demonstrates pydantic-settings dependency injection."""
    return {"app_name": s.app_name, "debug": s.debug}


@app.get("/api/hello", response_model=HelloResponse)
@limiter.limit(settings.rate_limit)
async def hello(request: Request):
    """Sample API endpoint"""
    return {"message": "Hello from FastAPI!"}


@app.post("/api/items", response_model=CreateItemResponse, status_code=201)
async def create_item(item: Item):
    """Create a new item"""
    return {"status": "created", "item": item}


@app.get("/api/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int):
    """Get item by ID"""
    return {"item_id": item_id, "name": f"Item {item_id}", "price": 99.99}


# BackgroundTasks is appropriate for fast, fire-and-forget operations (email hooks,
# audit logs) that don't need retries or persistence. For retries, persistence, or
# distributed execution across processes/servers, use a proper task queue (Celery/ARQ).
@app.post("/api/v1/notify", status_code=202)
async def notify(notification: NotificationRequest, background_tasks: BackgroundTasks):
    """Queue a fire-and-forget email notification."""
    background_tasks.add_task(send_notification_email, notification.email, notification.message)
    return {"status": "queued"}


# EXAMPLE: Use async def for I/O-bound routes (DB queries, HTTP calls).
# async routes are non-blocking — the event loop can handle other requests
# while waiting for I/O to complete.
#
# @app.get("/api/example-async")
# async def example_async_route():
#     # await db.fetch_one(query)        ← non-blocking DB call
#     # await httpx_client.get(url)      ← non-blocking HTTP call
#     return {"message": "Hello from async route"}
#
# EXAMPLE: Use def (sync) only for CPU-bound work or sync-only libraries.
# FastAPI automatically runs sync routes in a threadpool to avoid blocking
# the event loop.
#
# @app.get("/api/example-sync")
# def example_sync_route():
#     # result = some_sync_library.compute()  ← CPU-bound or sync-only library
#     return {"message": "Hello from sync route"}


class TodoCreate(BaseModel):
    title: str = Field(min_length=1)

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
@app.get("/api/todos", response_model=list[TodoOut], tags=["todos"])
async def list_todos(db: AsyncSession = Depends(get_db)):
    """List all todo items. Demonstrates async SQLAlchemy query via Depends(get_db)."""
    result = await db.execute(select(TodoItem))
    return result.scalars().all()


@app.post("/api/todos", response_model=TodoOut, status_code=201, tags=["todos"])
async def create_todo(todo: TodoCreate, db: AsyncSession = Depends(get_db)):
    """Create a todo item. Demonstrates async SQLAlchemy write via Depends(get_db)."""
    item = TodoItem(title=todo.title)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
