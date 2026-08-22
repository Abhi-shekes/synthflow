import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
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
    """What this user changed, newest first.

    Scoped to the caller, and that is a limit rather than a choice: until
    projects can be shared there is nobody else whose activity would be
    appropriate to show, and a wider answer would be showing one person
    another person's work. When organisations land, this is the query that
    grows a role check rather than a new endpoint.

    Paged for the same reason the API-key list is: an audit log only ever
    grows, so "all of them" stops being a sensible response.
    """
    return audit.read(db, current_user.id, project_id=project_id, limit=limit, offset=offset)
