import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class PluginOutput(Base):
    """A background producer that delivers freshly generated rows for one
    entity to a third-party output plugin — the output half of Phase 5's
    plugin framework, alongside the generator and rule-function halves
    (see app.services.plugins). Same execution model as KafkaOutput/
    MQTTOutput: an `asyncio.Task` (app.services.plugin_output_producers)
    started when this row is created and cancelled when it's deleted, not
    resumed on restart, single-process only.

    Where this differs from Kafka/MQTT: those are first-party typed
    models with a fixed config shape (bootstrap_servers/topic, etc.) —
    this one is generic, since a plugin's config shape isn't known until
    it's installed. `plugin_name` selects which installed
    `synthflow.outputs` entry point handles delivery; `config` is
    whatever free-form JSON that plugin's `deliver_batch(config, rows)`
    expects, validated by the plugin itself, not by this model or its
    routes.
    """

    __tablename__ = "plugin_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    plugin_name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
