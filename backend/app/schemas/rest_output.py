import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RestOutputCreate(BaseModel):
    default_count: int = 10


class RestOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    token: str
    default_count: int
    created_at: datetime
