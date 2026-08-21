import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class KafkaOutput(Base):
    """A background producer that publishes freshly generated rows for one
    entity to a Kafka topic — one JSON message per row, at
    `1/events_per_second` — for as long as the backend process runs.

    This is the "real background-task execution model" WebSocketStream's
    docstring flagged as needed for Kafka/MQTT instead of its own
    connection-scoped loop: a broker has no client connection to hang
    production on, so the loop has to run independently. See
    app.services.stream_producers for the actual mechanics — an
    `asyncio.Task` tracked in a module-level registry, started when this
    row is created and cancelled when it's deleted.

    Deliberately NOT resumed automatically if the backend process
    restarts — a `KafkaOutput` row surviving a restart with no running
    producer is a documented gap, not a silent one, the same kind of
    tradeoff `WebSocketStream` already accepts by not persisting "running"
    state at all. Single-process only: running multiple backend workers
    would start independent, duplicate producers for the same output —
    fine for this project's single-container docker-compose deployment,
    not something to rely on beyond that.
    """

    __tablename__ = "kafka_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    bootstrap_servers: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
