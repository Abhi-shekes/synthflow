import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


def _generate_token() -> str:
    return secrets.token_urlsafe(24)


class RestOutput(Base):
    """A public, unauthenticated read endpoint for one entity's generated
    data: `GET /public/rest/{token}` — meant for a frontend developer to point
    `fetch()` at directly during development, the way a mock-API tool would,
    without needing a SynthFlow account. `token` is a capability URL, not a
    password: possessing it is exactly the access control, the same trust
    model as a webhook URL or a Figma share link. Each call generates a fresh
    batch (respecting the entity's rules/workflows) — there's no snapshot or
    caching, so repeated calls return different rows, not the same ones."""

    __tablename__ = "rest_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_generate_token)
    default_count: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity: Mapped["Entity"] = relationship()
