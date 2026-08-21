import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.field import EntityField
    from app.models.lookup_table import LookupTable


class LookupAttachment(Base):
    """Attaches one field to a column of a project-level LookupTable: instead
    of being randomized independently, the field draws a value from that
    column's real data (see app.services.generator.build_lookup_pools, which
    feeds the attached column's values into the same pool mechanism
    relationships already use for foreign keys — `field.unique` on the
    attached field controls draw-with/without-replacement exactly as it does
    for a relationship's foreign-key field).

    Unlike a Relationship, a lookup doesn't need another entity generated
    first — the reference data already exists at upload time — so a lookup
    works in single-entity generation too, not just project-wide generation.
    If a field ends up with both a Relationship and a LookupAttachment
    (not cross-validated against each other, same as Trend/Workflow aren't),
    the lookup pool wins: see generate_project's docstring for that merge
    order.
    """

    __tablename__ = "lookup_attachments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), unique=True
    )
    lookup_table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lookup_tables.id", ondelete="CASCADE")
    )
    column: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["EntityField"] = relationship()
    lookup_table: Mapped["LookupTable"] = relationship(back_populates="attachments")
