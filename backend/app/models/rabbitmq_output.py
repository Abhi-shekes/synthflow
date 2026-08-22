import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.secrets import EncryptedString
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class RabbitMQOutput(Base):
    """A background producer that publishes generated rows to a RabbitMQ
    exchange — one JSON message per row.

    Third broker of the same shape as `KafkaOutput` and `MQTTOutput`, and
    deliberately spelled the same way: separate host/port/credential
    columns rather than one `amqp://user:pass@host/vhost` URL. A URL would
    bury the password in a field the UI has to show, whereas separate
    columns let the password alone be encrypted and omitted from the read
    API — the same split `DatabaseConnection` uses.

    An empty `exchange` means RabbitMQ's default exchange, where the
    routing key is the queue name. That is the simplest thing that works
    for someone who just wants messages to arrive in a queue.
    """

    __tablename__ = "rabbitmq_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=5672)
    vhost: Mapped[str] = mapped_column(String(255), nullable=False, default="/")
    username: Mapped[str] = mapped_column(String(255), nullable=False, default="guest")
    password: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    exchange: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    routing_key: Mapped[str] = mapped_column(String(255), nullable=False)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
