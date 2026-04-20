import logging
import math
import os
import time
from collections import Counter
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from database import Base, engine
from routes import HealthResponse, HelloResponse, InfoResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "FastAPI Starter"
    debug: bool = False
    secret_key: str = "change-me-in-production-not-for-real-use"
    allowed_origins: list[str] = ["http://localhost:3000"]
    allowed_hosts: list[str] = ["*"]
    rate_limit: str = "100/minute"

    @field_validator('rate_limit')
    @classmethod
    def rate_limit_must_be_valid_format(cls, v: str) -> str:
        import re
        if not re.compile(r'^[1-9]\d*/(second|minute|hour|day)s?$', re.IGNORECASE).match(v.strip()):
            raise ValueError(f'RATE_LIMIT must be in format "<count>/<period>" (e.g. "100/minute"). Got: {v!r}')
        return v

    @field_validator('secret_key')
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        _gen = 'python -c "import secrets; print(secrets.token_hex(32))"'
        if len(v) < 32:
            raise ValueError(f'SECRET_KEY must be at least 32 characters. Generate with: {_gen}')
        counts = Counter(v)
        entropy = -sum((c / len(v)) * math.log2(c / len(v)) for c in counts.values())
        if entropy < 3.0:
            raise ValueError(f'SECRET_KEY entropy too low — use a randomly generated key. Generate with: {_gen}')
        return v


settings = Settings()


def get_settings() -> Settings:
    return settings


STARTUP_TIME = time.time()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

# Evict route modules so reloading main re-evaluates their @limiter.limit() decorators.
import sys as _sys
for _mod in ("routes.items", "routes.todos", "routes.notify"):
    _sys.modules.pop(_mod, None)

from middleware.request_logging import RequestLoggingMiddleware  # noqa: E402
from middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402
from routes.items import router as items_router  # noqa: E402
from routes.notify import router as notify_router  # noqa: E402
from routes.todos import router as todos_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if not settings.debug and settings.allowed_hosts == ["*"]:
        logger.warning(
            "SECURITY WARNING: ALLOWED_HOSTS is set to '*' in production mode. "
            'Set ALLOWED_HOSTS env var to restrict accepted Host headers. Example: ALLOWED_HOSTS=["myapp.com"]'
        )
    if not settings.debug and settings.secret_key == "change-me-in-production-not-for-real-use":
        logger.warning(
            "SECURITY WARNING: SECRET_KEY is set to the publicly known default value. "
            'This key is not secret. Rotate before deploying: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    logger.info("Starting up")
    yield
    if engine is not None:
        await engine.dispose()
    logger.info("Shutting down")


app = FastAPI(
    title="Python FastAPI Starter", description="A minimal FastAPI backend starter template",
    version="1.0.0", debug=settings.debug, lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda req, exc: JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"}),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
if not settings.debug:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
if os.path.exists("dist"): app.mount("/static", StaticFiles(directory="dist"), name="static")  # noqa: E701


def _serializable_errors(errors: list) -> list:
    # field_validator stores exception in ctx['error'], which is not JSON serializable.
    result = []
    for e in errors:
        e = dict(e)
        if 'ctx' in e:
            e['ctx'] = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in e['ctx'].items()}
        result.append(e)
    return result


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={"detail": _serializable_errors(exc.errors()), "body": exc.body},
        headers={"X-Request-ID": request_id} if request_id else {},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception for %s %s (request_id=%s)", request.method, request.url.path, request_id
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={"X-Request-ID": request_id} if request_id else {},
    )


@app.get("/")
@limiter.limit(settings.rate_limit)
def root(request: Request):
    if os.path.exists("dist/index.html"):
        with open("dist/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    return {"message": "FastAPI Backend", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health_check():
    return {"status": "healthy", "uptime_seconds": int(time.time() - STARTUP_TIME)}


@app.get("/info", tags=["info"], response_model=InfoResponse)
@limiter.limit(settings.rate_limit)
async def info(request: Request, s: Settings = Depends(get_settings)):
    return {"app_name": s.app_name, "debug": s.debug}


@app.get("/api/hello", response_model=HelloResponse)
@limiter.limit(settings.rate_limit)
async def hello(request: Request):
    return {"message": "Hello from FastAPI!"}


app.include_router(items_router)
app.include_router(todos_router)
app.include_router(notify_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
