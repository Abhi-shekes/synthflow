import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.continuity import ChangeOperation, RecordStatus


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


class ApplyChangesRequest(BaseModel):
    """One tick of churn against a store's population.

    Counts rather than rates: a caller that wants "3% of rows change per
    minute" can work that out from the population size it already knows,
    and a rate would have meant this endpoint owning a clock.
    """

    inserts: int = Field(default=0, ge=0, le=10_000)
    updates: int = Field(default=0, ge=0, le=10_000)
    deletes: int = Field(default=0, ge=0, le=10_000)

    # None means every changeable field. The identity field and formula
    # fields are never in this set: changing an identity is a delete and an
    # insert wearing one event's clothing, and a formula field is derived.
    update_fields: list[str] | None = None


class ChangeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    operation: ChangeOperation
    identity: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    version: int
    created_at: datetime


class ApplyChangesResponse(BaseModel):
    events: list[ChangeEventRead]
    # Where a consumer should resume from. Returned rather than left to be
    # derived from the last event, because a call that changed nothing still
    # has a correct cursor to report.
    next_sequence: int
    total_active: int
