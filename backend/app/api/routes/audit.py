import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventRead
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
def list_audit_events(
    project_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    """Newest-first: everyone's activity on `project_id` if given and the
    caller can see that project (a shared project's audit trail is for the
    whole team, not filtered down to one member's own actions — see
    `app.services.audit.read`), otherwise just what this user changed.

    Paged for the same reason the API-key list is: an audit log only ever
    grows, so "all of them" stops being a sensible response.
    """
    if project_id is not None:
        _get_owned_project(project_id, current_user, db)
    return audit.read(db, current_user.id, project_id=project_id, limit=limit, offset=offset)
