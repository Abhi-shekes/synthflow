import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.secrets import EncryptedString
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class WebhookOutput(Base):
    """A background producer that POSTs batches of generated rows to a URL,
    signed so the receiver can prove they came from this SynthFlow.

    The opposite direction from `RestOutput`, which is a *pull* endpoint
    anyone with the token can fetch from. This pushes, which means the
    receiver cannot rely on a secret URL to know a request is genuine —
    hence the signature. See app.services.webhook_signing for the scheme
    and what it does and does not prove.

    Same execution model as the Kafka and MQTT producers: its own
    asyncio.Task, started on create and cancelled on delete, resumed after
    a restart by `jobs.resume_producers`.
    """

    __tablename__ = "webhook_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Shared with the receiver, encrypted here for the same reason a
    # database password is: possessing it is what lets someone forge a
    # request that looks like ours.
    secret: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    events_per_second: Mapped[float] = mapped_column(Float, default=1.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
