import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkflowTransition(BaseModel):
    source: str
    target: str


class WorkflowCreate(BaseModel):
    field_id: uuid.UUID
    states: list[str]
    initial_states: list[str]
    transitions: list[WorkflowTransition]


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    states: list[str]
    initial_states: list[str]
    transitions: list[WorkflowTransition]
    created_at: datetime
