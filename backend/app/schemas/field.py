import uuid

from pydantic import BaseModel, ConfigDict

from app.models.field import FieldType


class EntityFieldCreate(BaseModel):
    name: str
    field_type: FieldType
    order: int = 0
    required: bool = False
    nullable: bool = True
    unique: bool = False
    default_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    enum_values: list[str] | None = None


class EntityFieldUpdate(BaseModel):
    name: str | None = None
    field_type: FieldType | None = None
    order: int | None = None
    required: bool | None = None
    nullable: bool | None = None
    unique: bool | None = None
    default_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    enum_values: list[str] | None = None


class EntityFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    field_type: FieldType
    order: int
    required: bool
    nullable: bool
    unique: bool
    default_value: str | None
    min_value: float | None
    max_value: float | None
    regex: str | None
    enum_values: list[str] | None
