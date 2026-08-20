import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.field import EntityFieldRead
from app.schemas.rule import RuleRead


class EntityCreate(BaseModel):
    name: str


class EntityUpdate(BaseModel):
    name: str | None = None


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    fields: list[EntityFieldRead] = []
    rules: list[RuleRead] = []


class GenerateRequest(BaseModel):
    count: int = 10
