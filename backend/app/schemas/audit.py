import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit import ActorKind


class AuditEventRead(BaseModel):
    """One recorded change.

    `route` is the route *template*, not the concrete path — templates are a
    small set that groups and filters, concrete paths are unbounded and group
    into nothing. `path_params` carries the ids that were in it.

    `actor_email` and `api_key_prefix` are denormalised copies rather than
    joins, so an event still says who did it after the user or the key has
    been deleted.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_email: str | None
    actor_kind: ActorKind
    api_key_prefix: str | None
    method: str
    route: str
    status_code: int
    project_id: uuid.UUID | None
    path_params: dict[str, str]
    created_at: datetime
