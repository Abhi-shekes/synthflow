import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.error_injection import ErrorType


class ErrorInjectionCreate(BaseModel):
    field_id: uuid.UUID
    rate: float = Field(gt=0, le=1)
    error_types: list[ErrorType]


class ErrorInjectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    rate: float
    error_types: list[ErrorType]
    created_at: datetime
