import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.error_injection import ErrorInjectionRead
from app.schemas.field import EntityFieldRead
from app.schemas.lookup_attachment import LookupAttachmentRead
from app.schemas.rule import RuleRead
from app.schemas.trend import TrendRead
from app.schemas.workflow import WorkflowRead


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
    workflows: list[WorkflowRead] = []
    trends: list[TrendRead] = []
    error_injections: list[ErrorInjectionRead] = []
    lookup_attachments: list[LookupAttachmentRead] = []


class GenerateRequest(BaseModel):
    count: int = 10
