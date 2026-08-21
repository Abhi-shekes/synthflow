import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.field import EntityField


class ErrorType(enum.StrEnum):
    NULL = "null"
    EMPTY = "empty"
    DUPLICATE = "duplicate"
    TRUNCATE = "truncate"
    WRONG_TYPE = "wrong_type"
    OUT_OF_RANGE = "out_of_range"


class ErrorInjection(Base):
    """Deliberately corrupts a field's already-computed value on some
    fraction of generated rows (`rate`, 0–1), chosen from `error_types` —
    simulating the bad data a real pipeline has to handle: nulls in required
    fields, duplicate ids, truncated strings, wrong-typed values, out-of-range
    numbers. Applied *after* a field's value is otherwise fully generated
    (formula, trend, workflow, or plain random) — corruption doesn't care how
    the clean value was produced, it just replaces it on some rows (see
    app.services.generator._corrupt_value).

    Known interaction: a rule evaluates the row *after* corruption, so a
    corrupted value that violates a rule gets the whole row discarded and
    regenerated — rules act as a quality gate that can quietly filter out the
    very corruption you configured. Don't combine error injection with a rule
    constraining the same field if you need guaranteed corrupted output.
    """

    __tablename__ = "error_injections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), unique=True
    )
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    error_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["EntityField"] = relationship()
