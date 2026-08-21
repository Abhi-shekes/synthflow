import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class MQTTOutput(Base):
    """A background producer that publishes freshly generated rows for one
    entity to an MQTT topic — one JSON message per row, at
    `1/events_per_second` — for as long as the backend process runs.

    Same design as `KafkaOutput` (see that model's docstring for the full
    reasoning): a broker has no client connection to hang production on,
    so this runs as its own `asyncio.Task` (see
    app.services.stream_producers), started on create and cancelled on
    delete, not resumed across a backend restart, single-process only.
    """

    __tablename__ = "mqtt_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    broker_host: Mapped[str] = mapped_column(String(255), nullable=False)
    broker_port: Mapped[int] = mapped_column(Integer, default=1883)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
