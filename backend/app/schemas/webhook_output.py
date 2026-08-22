import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WebhookOutputCreate(BaseModel):
    url: str
    secret: str
    events_per_second: float = Field(default=1.0, gt=0)
    batch_size: int = Field(default=1, gt=0)


class WebhookOutputRead(BaseModel):
    """Never includes `secret` — it is what lets someone forge a request
    that looks like ours, so the same rule applies as to a database
    password."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    url: str
    events_per_second: float
    batch_size: int
    created_at: datetime
