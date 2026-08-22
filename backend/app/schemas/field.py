import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.field import FieldType

# preset is deliberately `str` rather than a closed Enum union: since
# app.services.plugins can surface preset names from installed third-party
# packages at runtime, the valid set isn't known at schema-definition time
# any more. Membership is checked dynamically instead, in
# app.api.routes.entities.validate_preset against
# app.services.plugins.available_presets().


class EntityFieldCreate(BaseModel):
    name: str
    field_type: FieldType
    order: int = 0
    required: bool = False
    nullable: bool = True
    unique: bool = False
    # How often this field generates NULL. None means "use the engine
    # default" (15%), which is not the same as an explicit 0.0 — that means
    # never null, and is a real thing to ask for.
    null_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    default_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    preset: str | None = None
    enum_values: list[str] | None = None
    enum_weights: list[float] | None = None
    formula: str | None = None


class EntityFieldUpdate(BaseModel):
    name: str | None = None
    field_type: FieldType | None = None
    order: int | None = None
    required: bool | None = None
    nullable: bool | None = None
    unique: bool | None = None
    null_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    default_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    preset: str | None = None
    enum_values: list[str] | None = None
    enum_weights: list[float] | None = None
    formula: str | None = None


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
    null_probability: float | None
    default_value: str | None
    min_value: float | None
    max_value: float | None
    regex: str | None
    preset: str | None
    enum_values: list[str] | None
    enum_weights: list[float] | None
    formula: str | None
