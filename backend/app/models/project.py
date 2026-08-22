import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Nullable: a project without an organisation is personal and behaves
    # exactly as it did before organisations existed. Sharing is something
    # you opt a project into, rather than a concept a single-user install
    # has to carry. `SET NULL` on delete, so dissolving an organisation
    # returns its projects to their owners instead of destroying them.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # The next version-history snapshot's number. A real counter rather than
    # `max(version) + 1` over the existing rows: deleting the most recent
    # snapshot would lower that maximum, and the next snapshot would reuse a
    # number somebody may have referred to last week — "roll back to v3"
    # would quietly mean a different design.
    next_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    entities: Mapped[list["Entity"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
