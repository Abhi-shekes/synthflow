import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.template import ProjectTemplate


class VersionCreate(BaseModel):
    # Optional, because forcing one just produces "v4". "before the pricing
    # rework" is worth more than a timestamp, and only a person can write it.
    label: str | None = Field(default=None, max_length=255)


class VersionRead(BaseModel):
    """A version's metadata, without its payload.

    The template is deliberately absent: a list of twenty versions should
    not ship twenty full project designs to render twenty rows.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    label: str | None
    created_by_email: str | None
    created_at: datetime


class VersionDetail(VersionRead):
    template: ProjectTemplate


class VersionDiff(BaseModel):
    """Structural, not textual.

    A JSON text diff of two templates answers no question anyone has: it
    reports a list reordering when nothing changed, and buries "the `email`
    field became nullable" in forty lines of context.
    """

    from_version: int
    to_version: int
    identical: bool
    name_changed: dict[str, Any] | None
    entities_added: list[str]
    entities_removed: list[str]
    entities_changed: list[dict[str, Any]]
    counts: dict[str, dict[str, int]]


class RollbackRequest(BaseModel):
    # A rollback deletes and rebuilds every entity, and a record store hangs
    # off an entity with ON DELETE CASCADE — so the stored populations go
    # with it. Refused unless the caller says they know.
    discard_record_stores: bool = False


class RollbackResult(BaseModel):
    restored_from: int
    # The snapshot taken of the pre-rollback state, so a rollback is itself
    # undoable. Rolling back is the one moment you most want a way back.
    backup_version: int
