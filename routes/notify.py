import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from main import limiter, settings

router = APIRouter(prefix="/api/v1", tags=["notify"])
logger = logging.getLogger(__name__)


class NotificationRequest(BaseModel):
    email: EmailStr
    message: str = Field(min_length=1, max_length=1000)

    @field_validator('message')
    @classmethod
    def message_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('message must not be blank')
        return v


class NotificationQueuedResponse(BaseModel):
    status: str


# Background task function — simulates a fire-and-forget email notification.
# async def can also be used here for non-blocking I/O in the background.
def send_notification_email(email: str, message: str) -> None:
    time.sleep(0.1)  # Simulate work (e.g., SMTP call)
    logger.info(json.dumps({"event": "notification_sent", "email": email}))


# BackgroundTasks is appropriate for fast, fire-and-forget operations (email hooks,
# audit logs) that don't need retries or persistence. For retries, persistence, or
# distributed execution across processes/servers, use a proper task queue (Celery/ARQ).
@router.post("/notify", status_code=202, response_model=NotificationQueuedResponse)
@limiter.limit(settings.rate_limit)
async def notify(request: Request, notification: NotificationRequest, background_tasks: BackgroundTasks):
    """Queue a fire-and-forget email notification."""
    background_tasks.add_task(send_notification_email, notification.email, notification.message)
    return {"status": "queued"}
