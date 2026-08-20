import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RelationshipType(enum.StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"
    PARENT_CHILD = "parent_child"


class Relationship(Base):
    """A directed link from a foreign-key field on one entity (the source) to the
    field it references on another entity (the target) within the same project.

    Generation-time semantics live in app.services.generator: target entities are
    generated first, and the source's foreign-key field draws its values from the
    already-generated target rows instead of being randomized independently.
    many_to_many is stored but currently generated the same way as one_to_many
    (each source row picks one target value) — true join-table modeling is a
    later enhancement.
    """

    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType), nullable=False
    )

    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE")
    )
    source_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE")
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE")
    )
    target_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
