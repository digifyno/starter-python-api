import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

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


settings = Settings()


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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from dist/ directory
if os.path.exists("dist"):
    app.mount("/static", StaticFiles(directory="dist"), name="static")


# Models
class HealthResponse(BaseModel):
    status: str
    message: str


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float


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


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="API is running")


@app.get("/api/hello")
async def hello():
    """Sample API endpoint"""
    return {"message": "Hello from FastAPI!"}


@app.post("/api/items")
async def create_item(item: Item):
    """Create a new item"""
    return {"status": "created", "item": item}


@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    """Get item by ID"""
    return {"item_id": item_id, "name": f"Item {item_id}", "price": 99.99}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
