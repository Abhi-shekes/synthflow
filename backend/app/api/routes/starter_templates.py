from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.template import ProjectTemplate, StarterTemplateSummary
from app.services.starter_templates import list_starter_templates, load_starter_template

router = APIRouter(prefix="/starter-templates", tags=["starter-templates"])


@router.get("", response_model=list[StarterTemplateSummary])
def list_starter_templates_route(
    current_user: User = Depends(get_current_user),
) -> list[StarterTemplateSummary]:
    return list_starter_templates()


@router.get("/{key}", response_model=ProjectTemplate)
def get_starter_template_route(
    key: str, current_user: User = Depends(get_current_user)
) -> ProjectTemplate:
    try:
        return load_starter_template(key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
