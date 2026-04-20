from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int


class HelloResponse(BaseModel):
    message: str


class InfoResponse(BaseModel):
    app_name: str
    debug: bool
