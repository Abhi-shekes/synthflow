import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.field import EntityField


class TrendType(enum.StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGISTIC = "logistic"
    SEASONAL = "seasonal"
    CYCLIC = "cyclic"
    RANDOM_WALK = "random_walk"


class Trend(Base):
    """Makes a numeric field's value a function of its row's 0-indexed
    position within the current batch, instead of an independent random draw
    each row — e.g. a linear trend produces a steadily rising column across
    a `generate` call. `params` holds type-specific values (see
    app.services.trends.REQUIRED_PARAMS for the exact keys per type) plus an
    optional `noise` stddev applied on top of any type. `increasing` and
    `decreasing` from the spec aren't separate types here — they're `linear`
    with a positive or negative `slope`; keeping the type list to the ones
    that are actually mathematically distinct.

    Position resets to 0 at the start of every `generate` call. That's a
    deliberate scope decision, not an oversight: a batch replays the trend
    from the start every time rather than continuing where the last call
    left off. For a WebSocket stream (see app.models.websocket_stream) this
    means each push replays the trend across its own batch_size rows rather
    than continuing smoothly tick to tick — genuine cross-tick continuity
    would mean persisting trend state on the stream itself, which hasn't
    been built (see TODO.md). random_walk is further affected by rules: a
    rule-rejected candidate still advances the walk's running state, the
    same accepted tradeoff already documented for unique-value pools in
    generate_rows()."""

    __tablename__ = "trends"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), unique=True
    )
    trend_type: Mapped[TrendType] = mapped_column(Enum(TrendType), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["EntityField"] = relationship()
