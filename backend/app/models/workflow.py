import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.field import EntityField


class Workflow(Base):
    """A state machine attached to one field on an entity: `states` is the node
    set, `initial_states` the subset a row may start from, and `transitions` a
    list of {"source": state, "target": state, "weight": float} edges — `weight`
    is optional per transition (default 1.0, i.e. uniform among a state's
    outgoing edges when omitted).

    Generation-time semantics live in app.services.generator: instead of
    picking a random value, a random walk is taken through the graph starting
    from a random initial state, stopping early with some probability at each
    step (bounded by MAX_WORKFLOW_STEPS). The field is set to the walk's final
    state, and the full walk is exposed alongside it as `<field>_history` —
    this is what makes it a simulated *progression* rather than a plain enum:
    later-in-the-graph states are naturally rarer, matching how a batch of
    real records would be caught at different points in a process.

    `stop_probabilities` (optional) maps a state name to the probability of
    stopping the walk right after reaching it, overriding the flat
    `generator.WORKFLOW_STOP_PROBABILITY` default for that state — a state
    with no entry keeps the default. This plus transition `weight` is what
    makes a Workflow a realistic engine for the roadmap's "user behavior
    simulation" funnels (e.g. login -> search -> cart -> checkout -> purchase):
    real drop-off isn't flat across every step, checkout abandons far more
    often than a search click does, and this is the one real gap that was
    closed rather than a new "funnel" concept — a funnel is already exactly
    what a linear Workflow chain produces.
    """

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), unique=True
    )

    states: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    initial_states: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    transitions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    stop_probabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["EntityField"] = relationship()
