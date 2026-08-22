import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.relationship import RelationshipType


class RelationshipCreate(BaseModel):
    relationship_type: RelationshipType
    source_entity_id: uuid.UUID
    source_field_id: uuid.UUID
    target_entity_id: uuid.UUID
    target_field_id: uuid.UUID

    # many_to_many only: how many targets each source row links to. A range
    # rather than a constant, because a constant count is the tell that a
    # dataset was generated.
    min_links: int = Field(default=1, ge=0, le=1000)
    max_links: int = Field(default=3, ge=0, le=1000)

    @model_validator(mode="after")
    def _links_make_sense(self) -> "RelationshipCreate":
        if self.max_links < self.min_links:
            raise ValueError("max_links must not be less than min_links")
        return self


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    relationship_type: RelationshipType
    source_entity_id: uuid.UUID
    source_field_id: uuid.UUID
    target_entity_id: uuid.UUID
    target_field_id: uuid.UUID
    min_links: int
    max_links: int
    created_at: datetime


class ProjectGenerateRequest(BaseModel):
    count: int = 10
    counts: dict[uuid.UUID, int] = {}
