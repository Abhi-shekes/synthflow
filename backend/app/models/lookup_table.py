import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lookup_attachment import LookupAttachment
    from app.models.timeline_replay import TimelineReplay

PREVIEW_ROWS = 5


class LookupTable(Base):
    """Reference data uploaded once per project (CSV/Excel/JSON) and reused
    by any field via a LookupAttachment — see that model for how a field
    draws from a specific column (app.services.generator.build_lookup_pools).

    Stored as parsed JSON (`columns` + `data`) rather than as its own SQL
    table: a project's lookup tables are typically small reference lists
    (a few thousand rows at most, enforced by settings.MAX_LOOKUP_ROWS at
    upload time — see app.services.lookup_tables), so a blob avoids the
    complexity of a dynamic-schema SQL table for no real benefit. `data`
    values keep whatever type they came in with — native JSON types for a
    `.json` upload, best-effort int/float coercion for CSV/Excel since those
    formats are text-only on disk (see
    app.services.lookup_tables.coerce_numeric).
    """

    __tablename__ = "lookup_tables"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    columns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ORM-level cascade rather than relying solely on the FK's ondelete=CASCADE:
    # SQLite (used for local dev/tests, unlike the Postgres default in docker
    # compose) doesn't enforce FK constraints unless a PRAGMA is set, which
    # this app doesn't set — so deleting a lookup table would silently orphan
    # its attachments there without this.
    attachments: Mapped[list["LookupAttachment"]] = relationship(
        back_populates="lookup_table",
        cascade="all, delete-orphan",
        order_by="LookupAttachment.created_at",
    )
    replays: Mapped[list["TimelineReplay"]] = relationship(
        back_populates="lookup_table",
        cascade="all, delete-orphan",
        order_by="TimelineReplay.created_at",
    )

    @property
    def preview(self) -> list[dict[str, Any]]:
        return self.data[:PREVIEW_ROWS]
