import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
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

    **`many_to_many` is the exception, and it reads its two fields
    differently.** A many-to-many has no foreign key on either side — that is
    what makes it many-to-many — so the link cannot live on a row. For this
    type, `source_field` and `target_field` name each side's *own* key, and
    generation emits a **join table** pairing them (see
    `generator.generate_join_tables`). Each source row gets between
    `min_links` and `max_links` distinct targets.

    Until Phase 13 this type was stored but generated exactly like
    `one_to_many` — each source row drew one target value into its source
    field — which is a documented simplification now removed. A project that
    modelled a many-to-many that way was really modelling a one-to-many and
    should say so; the type now means what it says.
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

    # How many targets each source row links to, for many_to_many only.
    # A range rather than a fixed number because a real join table is
    # lumpy — a student takes three courses or seven, not always five — and
    # a constant count is the tell that a dataset was generated.
    min_links: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_links: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
