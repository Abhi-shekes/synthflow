import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectVersion(Base):
    """A snapshot of a project's design, taken on request.

    The payload is a `ProjectTemplate` — the same serialisation that already
    powers export and import, and reusing it is the whole reason this bullet
    was small. A separate versioning format would have been a second thing
    to keep in step with the schema, and the two would have drifted the
    first time a field type was added.

    **Snapshots are explicit, not automatic.** Recording a version on every
    mutation sounds thorough and produces a history nobody can read: fifty
    entries for one afternoon's editing, forty-nine of which are a field
    half-renamed. A snapshot is something you take when the design is at a
    point worth returning to, which is a judgement only a person can make.
    The exception is rollback, which snapshots first — see the route.

    `version` counts per project and is assigned from the highest existing
    one. It is a human-facing number ("v3"), which is why it is not the row
    id: a uuid is not something anyone says out loud.

    **What is not captured**: generated data, record stores, jobs, outputs
    and credentials. This is the *design*, and a version that also carried a
    project's data would be a backup, which is a different feature with very
    different storage costs.
    """

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_version_project_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Free text, and optional. "before the pricing rework" is worth more
    # than a timestamp, and forcing one would just produce "v4".
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    template: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Nullable with SET NULL: deleting a user must not delete the history of
    # what the project looked like, the same rule the audit log follows.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship()
