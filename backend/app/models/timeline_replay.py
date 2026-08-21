import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.tokens import generate_token
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lookup_table import LookupTable


class TimelineReplay(Base):
    """A public, unauthenticated live feed that replays an uploaded
    LookupTable's rows in their original timestamp order, at
    `speed_multiplier` times real time: `WS /public/replay/{token}` sends
    one row per tick, timed by the gap between that row's
    `timestamp_column` value and the previous row's, divided by
    `speed_multiplier` (a 1-hour gap at speed_multiplier=60 plays back in 1
    minute; see app.api.routes.timeline_replays for the clamping that keeps
    a huge time gap from stalling the stream, and a tiny/negative one from
    spinning).

    Reuses LookupTable's existing upload/parsing (see
    app.services.lookup_tables) instead of inventing a separate "historical
    dataset" concept — a timeline replay's source and a lookup table's
    reference data are the same shape of thing (project-level uploaded
    CSV/Excel/JSON), just consumed differently: one is sampled from at
    generation time, the other is walked in order against a clock.

    Connection-scoped the same way WebSocketStream is: no persisted
    "running" state, the production loop *is* the WebSocket handler's loop.
    After the last row, playback loops back to the first — a timeline
    replay plays its historical window on repeat for as long as a client
    stays connected, rather than a one-shot playback that ends. Unlike
    WebSocketStream, the schedule is loaded once per connection rather than
    re-queried every tick — the source data doesn't change once uploaded,
    so there's no "did the config change" reason to hit the database again
    on every single row the way a fresh random batch does.

    `timestamp_column`'s values must be ISO-8601 strings (Python's
    `datetime.fromisoformat`, which accepts a trailing "Z") — validated
    against every row at creation time, not just spot-checked.
    """

    __tablename__ = "timeline_replays"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    lookup_table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lookup_tables.id", ondelete="CASCADE")
    )
    timestamp_column: Mapped[str] = mapped_column(String(255), nullable=False)
    speed_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=generate_token)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lookup_table: Mapped["LookupTable"] = relationship(back_populates="replays")
