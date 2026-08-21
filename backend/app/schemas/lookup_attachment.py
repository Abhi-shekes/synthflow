import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LookupAttachmentCreate(BaseModel):
    field_id: uuid.UUID
    lookup_table_id: uuid.UUID
    column: str


class LookupAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    lookup_table_id: uuid.UUID
    column: str
    created_at: datetime
