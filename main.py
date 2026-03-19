import json
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "FastAPI Starter"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    allowed_origins: list[str] = ["http://localhost:3000"]
    allowed_hosts: list[str] = ["*"]  # Override in production: ALLOWED_HOSTS=["yourdomain.com"]


settings = Settings()

STARTUP_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up")
    yield
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

# 1. CORS — reads from settings.allowed_origins (not wildcard!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
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
        # Note: Strict-Transport-Security (HSTS) is intentionally omitted here.
        # HSTS must be set at the nginx/reverse-proxy level to avoid accidentally
        # enabling HSTS on HTTP connections, which would break non-HTTPS environments.
        return response


app.add_middleware(SecurityHeadersMiddleware)


# 5. Request logging middleware — logs method, path, status, duration_ms as JSON.
#    /health is excluded to reduce noise. No query params or body (no PII).
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            json.dumps({
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            })
        )
        return response


app.add_middleware(RequestLoggingMiddleware)

# Serve static files from dist/ directory
if os.path.exists("dist"):
    app.mount("/static", StaticFiles(directory="dist"), name="static")


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Models
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float


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


@app.get("/api/hello", response_model=HelloResponse)
async def hello():
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
