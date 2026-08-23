import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.tokens import generate_token
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class WebSocketStream(Base):
    """A public, unauthenticated live feed for one entity's generated data:
    `WS /public/stream/{token}` pushes a fresh batch every `1/events_per_second`
    while a client stays connected.

    Deliberately connection-scoped rather than a persistent background
    producer: there is no "running" state to track in the database, because
    the production loop *is* the WebSocket handler's loop — it starts when a
    client connects and stops the moment they disconnect. That's the right
    shape for WebSocket specifically, where a client connection already gives
    you a lifecycle to hang the loop on. Kafka/MQTT outputs (not built yet)
    won't have that — a broker has no equivalent open connection to the
    caller — so they'll need an actual background-task execution model
    instead of copying this pattern.
    """

    __tablename__ = "websocket_streams"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=generate_token)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
