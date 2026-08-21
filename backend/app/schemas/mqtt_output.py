import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MQTTOutputCreate(BaseModel):
    broker_host: str
    broker_port: int = Field(default=1883, ge=1, le=65535)
    topic: str
    events_per_second: float = Field(default=1.0, gt=0, le=50)
    batch_size: int = Field(default=1, ge=1, le=100)


class MQTTOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    broker_host: str
    broker_port: int
    topic: str
    events_per_second: float
    batch_size: int
    created_at: datetime
