import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.api_key import ApiKeyScope


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Full by default, because a key that cannot do what you needed it for
    # is a key you replace with a full one five minutes later. Read-only is
    # the deliberate choice, not the accidental one.
    scope: ApiKeyScope = ApiKeyScope.FULL
    # Null means it never expires. Offered rather than required: a key that
    # expires is better practice, and a key that expires without anyone
    # having planned for it is an outage.
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    """Never includes the secret. Same rule as connection passwords and
    storage keys: a credential readable from the API is a credential that
    leaks through logs, browser history and screenshots.

    `prefix` is here so a person can tell two keys apart in a list — it is
    the public half, and the only part of the key that survives creation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scope: ApiKeyScope
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    """The one response that carries the secret.

    A separate model rather than an optional field on `ApiKeyRead`, so it is
    impossible to return the secret by accident from a list or a fetch: the
    only route that can is the one that names this type.
    """

    key: str
