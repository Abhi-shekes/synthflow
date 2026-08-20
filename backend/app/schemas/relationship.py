import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.relationship import RelationshipType


class RelationshipCreate(BaseModel):
    relationship_type: RelationshipType
    source_entity_id: uuid.UUID
    source_field_id: uuid.UUID
    target_entity_id: uuid.UUID
    target_field_id: uuid.UUID


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    relationship_type: RelationshipType
    source_entity_id: uuid.UUID
    source_field_id: uuid.UUID
    target_entity_id: uuid.UUID
    target_field_id: uuid.UUID
    created_at: datetime


class ProjectGenerateRequest(BaseModel):
    count: int = 10
    counts: dict[uuid.UUID, int] = {}
