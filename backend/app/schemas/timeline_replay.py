import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TimelineReplayCreate(BaseModel):
    lookup_table_id: uuid.UUID
    timestamp_column: str
    speed_multiplier: float = Field(default=1.0, gt=0, le=1_000_000)


class TimelineReplayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    lookup_table_id: uuid.UUID
    timestamp_column: str
    speed_multiplier: float
    token: str
    created_at: datetime
