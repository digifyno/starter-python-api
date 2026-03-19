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

## Environment Variables

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
```

## Database Integration

### SQLAlchemy (PostgreSQL)
```bash
pip install sqlalchemy psycopg2-binary
```

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
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

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
