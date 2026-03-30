# Python FastAPI Starter Template

A minimal, production-ready FastAPI backend starter template.

## Features

- **FastAPI** - Modern, high-performance Python web framework
- **Uvicorn** - Lightning-fast ASGI server
- **Pydantic** - Data validation using Python type hints
- **Auto-generated API Docs** - Interactive Swagger UI and ReDoc
- **Type Hints** - Full Python type safety

## Quick Start

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python main.py
# Or use uvicorn directly:
# uvicorn main:app --reload

# Visit http://localhost:8000
# API docs: http://localhost:8000/docs (only available when DEBUG=true)
```

## Project Structure

```
├── main.py              # FastAPI application, settings, middleware, routes
├── auth.py              # JWT token helpers and bcrypt password hashing
├── database.py          # Async SQLAlchemy engine and models
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Dev/test dependencies
├── pytest.ini           # Pytest configuration
├── .env.example         # Environment variable template
├── tests/               # Test suite
└── dist/                # Static files (optional)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint (serves dist/index.html or API info) |
| GET | `/health` | Health check |
| GET | `/info` | App name and debug flag |
| GET | `/api/hello` | Sample API endpoint |
| POST | `/api/items` | Create an item |
| GET | `/api/items/{item_id}` | Get item by ID |
| GET | `/api/todos` | List all todo items |
| POST | `/api/todos` | Create a todo item |
| POST | `/api/v1/notify` | Queue an email notification |

## Interactive Documentation

FastAPI automatically generates two types of interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs (only available when DEBUG=true)
- **ReDoc**: http://localhost:8000/redoc (only available when DEBUG=true)
- In production (DEBUG=false), API docs are disabled for security

## Adding Endpoints

```python
@app.get("/api/users")
async def get_users():
    return {"users": []}

@app.post("/api/users")
async def create_user(user: User):
    return {"user": user}
```

## Environment Variables

Copy `.env.example` to `.env` and set values. Configuration is loaded via pydantic-settings:

```env
# Required in production
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">

# Optional
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
ALLOWED_ORIGINS=["https://myapp.com"]
ALLOWED_HOSTS=["myapp.com","www.myapp.com"]
DEBUG=false
RATE_LIMIT=100/minute
```

## Database Integration

### PostgreSQL with SQLAlchemy (async)

```bash
# Async PostgreSQL (already included in requirements.txt)
pip install sqlalchemy>=2.0 asyncpg
```

### MongoDB

```bash
pip install motor
```

## Production Deployment

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## nginx Configuration

```nginx
location / {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## License

MIT
