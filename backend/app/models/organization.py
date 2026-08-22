import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Role(enum.StrEnum):
    """What a member may do, as a ladder rather than a matrix.

    Four levels, each strictly containing the one below it. A matrix of
    independent permissions is more expressive and, in practice, is a thing
    nobody can reason about: "can this person delete an entity" becomes a
    lookup rather than something you know from their title. The ladder is
    the shape almost every team actually wants.

    * **VIEWER** reads. Useful for the person who needs to see a schema
      without being able to change it.
    * **MEMBER** reads and writes — entities, fields, generation, jobs. The
      ordinary working role.
    * **ADMIN** additionally manages membership and can delete projects.
    * **OWNER** additionally manages the organisation itself, and cannot be
      removed by an admin. There is always at least one.

    The ordering is what `Role.allows` compares, so adding a level later
    means inserting it in `_ORDER` rather than revisiting every check.
    """

    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"

    def allows(self, needed: "Role") -> bool:
        return _ORDER[self] >= _ORDER[needed]


_ORDER: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.MEMBER: 1,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}


class Organization(Base):
    """A group of people who share projects.

    Projects stay ownable by a person: `Project.organization_id` is
    nullable, and a project without one behaves exactly as it did before
    organisations existed. That is deliberate — the alternative, giving
    everyone a personal organisation and migrating every project into it, is
    the model GitHub uses and it makes a single-user install carry a concept
    it never needed. Sharing is something you opt a project into.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(Base):
    """One person's role in one organisation.

    A person appears at most once per organisation — enforced by a unique
    constraint rather than by application code, because two rows with
    different roles is a question with no correct answer and the database is
    the only place that can refuse it under concurrency.
    """

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.MEMBER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()
