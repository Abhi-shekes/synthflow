import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class FieldType(enum.StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"
    JSON = "json"


class EntityField(Base):
    __tablename__ = "entity_fields"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(Enum(FieldType), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    required: Mapped[bool] = mapped_column(Boolean, default=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    unique: Mapped[bool] = mapped_column(Boolean, default=False)

    default_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    regex: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enum_values: Mapped[list | None] = mapped_column(JSON, nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="fields")
