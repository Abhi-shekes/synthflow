import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.trend import TrendType


class TrendCreate(BaseModel):
    field_id: uuid.UUID
    trend_type: TrendType
    params: dict[str, float]


class TrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    trend_type: TrendType
    params: dict[str, float]
    created_at: datetime
