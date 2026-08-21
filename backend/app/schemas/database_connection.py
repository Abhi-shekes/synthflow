import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.database_connection import DatabaseDialect


class DatabaseConnectionCreate(BaseModel):
    name: str
    dialect: DatabaseDialect
    host: str
    port: int
    database: str
    username: str
    password: str


class DatabaseConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    dialect: DatabaseDialect
    host: str
    port: int
    database: str
    username: str
    created_at: datetime


class DatabaseConnectionTestResult(BaseModel):
    ok: bool
    detail: str


class DatabasePushRequest(BaseModel):
    entity_id: uuid.UUID
    count: int = 10
    table_name: str | None = None


class DatabasePushResult(BaseModel):
    table: str
    rows_written: int
