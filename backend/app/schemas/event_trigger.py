import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventTriggerCreate(BaseModel):
    label: str = Field(min_length=1)
    condition: str


class EventTriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    label: str
    condition: str
    created_at: datetime
