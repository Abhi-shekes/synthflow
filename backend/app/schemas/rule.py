import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RuleCreate(BaseModel):
    condition: str


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    condition: str
    created_at: datetime
