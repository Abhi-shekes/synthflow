import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.object_storage import StorageProvider


class ObjectStorageTargetCreate(BaseModel):
    name: str
    provider: StorageProvider = StorageProvider.S3
    bucket: str
    # Empty means the bucket root, and empty means real AWS — both are the
    # common case, so neither is required.
    prefix: str = ""
    region: str = "us-east-1"
    endpoint_url: str = ""
    access_key_id: str
    secret_access_key: str


class ObjectStorageTargetRead(BaseModel):
    """Never includes `secret_access_key`. Same rule as
    DatabaseConnectionRead and the password it omits: a credential that can
    be read back out of the API is a credential that leaks through logs,
    browser history and screenshots."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    provider: StorageProvider
    bucket: str
    prefix: str
    region: str
    endpoint_url: str
    access_key_id: str
    created_at: datetime


class ObjectStorageTestResult(BaseModel):
    ok: bool
    detail: str
