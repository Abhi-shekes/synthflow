import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import ProjectRead
from app.schemas.template import ProjectTemplate
from app.services.templates import export_project, import_project

router = APIRouter(prefix="/projects", tags=["templates"])


@router.get("/{project_id}/export", response_model=ProjectTemplate)
def export_project_template(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectTemplate:
    project = _get_owned_project(project_id, current_user, db)
    return export_project(project, db)


@router.post("/import", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def import_project_template(
    payload: ProjectTemplate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return import_project(payload, current_user.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
