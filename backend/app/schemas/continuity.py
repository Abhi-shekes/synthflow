import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.continuity import RecordStatus


class RecordStoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Required, not inferred. See RecordStore's docstring: guessing which
    # field identifies a record is exactly the kind of silent decision that
    # makes a CDC stream wrong in a way nobody notices until downstream.
    identity_field_id: uuid.UUID


class RecordStoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    identity_field_id: uuid.UUID
    position: int
    created_at: datetime
    updated_at: datetime


class RecordStoreStats(RecordStoreRead):
    """A store plus what is actually in it.

    Separate from `RecordStoreRead` because the counts are two aggregate
    queries, and listing twenty stores should not run forty of them.
    """

    active_records: int
    deleted_records: int


class StoredRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    identity: str
    data: dict[str, Any]
    sequence: int
    version: int
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class GenerateIntoStoreRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=10_000)


class GenerateIntoStoreResponse(BaseModel):
    """The rows generated, plus where the cursor ended up.

    The rows are returned as well as stored because a store records that a
    record *exists*; it does not replace the output. A caller that wants the
    data still gets it in the response.
    """

    rows: list[dict[str, Any]]
    position: int
    total_active: int
