import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTransition(BaseModel):
    source: str
    target: str
    weight: float = Field(default=1.0, gt=0)


class WorkflowCreate(BaseModel):
    field_id: uuid.UUID
    states: list[str]
    initial_states: list[str]
    transitions: list[WorkflowTransition]
    stop_probabilities: dict[str, float] | None = None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    states: list[str]
    initial_states: list[str]
    transitions: list[WorkflowTransition]
    stop_probabilities: dict[str, float] | None
    created_at: datetime
