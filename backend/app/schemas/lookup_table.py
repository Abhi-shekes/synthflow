import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LookupTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    columns: list[str]
    row_count: int
    preview: list[dict[str, Any]]
    created_at: datetime
