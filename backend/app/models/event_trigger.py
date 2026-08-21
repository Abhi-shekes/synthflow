import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class EventTrigger(Base):
    """A threshold-style annotation on an entity: `condition` is the same
    kind of boolean expression a Rule uses (see app.services.expressions),
    evaluated against a fully-generated row — but unlike a Rule, a satisfied
    EventTrigger doesn't discard/regenerate the row. It's additive, not a
    filter: every trigger whose condition evaluates true for a row has its
    `label` appended to that row's `_triggered_events` list (a sibling to a
    Workflow field's `<field>_history` — an extra key alongside the declared
    fields, present in JSON/Excel output, dropped from CSV the same way
    `<field>_history` already is, since CSV has no place for a variable-
    length array column).

    Deliberately not wired to any external notification/webhook system —
    no email, Slack message, or HTTP callback fires when a trigger matches.
    "Firing" today means "visible in the generated data": a consumer greps
    or filters `_triggered_events` the same way they already would for any
    other field. Sending a real external notification is future work, once
    there's a reason to build the delivery mechanism for it (see TODO.md)."""

    __tablename__ = "event_triggers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="event_triggers")
