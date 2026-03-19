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
# API docs: http://localhost:8000/docs
```

## Project Structure

```
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── dist/                # Static files (optional)
│   └── index.html       # Placeholder page
└── .env                 # Environment variables (create this)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint (serves dist/index.html or API info) |
| GET | `/health` | Health check |
| GET | `/api/hello` | Sample API endpoint |
| POST | `/api/items` | Create an item |
| GET | `/api/items/{item_id}` | Get item by ID |

## Interactive Documentation

FastAPI automatically generates two types of interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost/dbname
SECRET_KEY=your-secret-key
DEBUG=True
```

Load in `main.py`:

```python
from dotenv import load_dotenv
load_dotenv()

database_url = os.getenv("DATABASE_URL")
```

## Database Integration

### PostgreSQL with SQLAlchemy

```bash
pip install sqlalchemy psycopg2-binary
```

### MongoDB

```bash
pip install motor
```

## Adding Authentication

To add JWT authentication, install the auth extras:

```bash
pip install -r requirements-auth.txt
```

Then follow the auth patterns in `CLAUDE.md`.

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
