import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GeoRouteCreate(BaseModel):
    field_id: uuid.UUID
    lookup_table_id: uuid.UUID
    lat_column: str
    lon_column: str


class GeoRouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    field_id: uuid.UUID
    lookup_table_id: uuid.UUID
    lat_column: str
    lon_column: str
    created_at: datetime
