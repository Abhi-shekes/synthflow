import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.error_injection import ErrorInjection
from app.models.field import EntityField
from app.models.user import User
from app.schemas.error_injection import ErrorInjectionCreate, ErrorInjectionRead
from app.services.error_injection import validate_error_types

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/error-injections",
    tags=["error-injections"],
)


@router.get("", response_model=list[ErrorInjectionRead])
def list_error_injections(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ErrorInjection]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.error_injections


@router.post("", response_model=ErrorInjectionRead, status_code=status.HTTP_201_CREATED)
def create_error_injection(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: ErrorInjectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ErrorInjection:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_id does not belong to this entity",
        )
    if any(e.field_id == payload.field_id for e in entity.error_injections):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This field already has error injection configured",
        )

    try:
        validate_error_types(field.field_type, payload.error_types)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    error_injection = ErrorInjection(
        entity_id=entity_id,
        field_id=payload.field_id,
        rate=payload.rate,
        error_types=payload.error_types,
    )
    db.add(error_injection)
    db.commit()
    db.refresh(error_injection)
    return error_injection


@router.delete("/{error_injection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_error_injection(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    error_injection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    error_injection = db.get(ErrorInjection, error_injection_id)
    if error_injection is None or error_injection.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error injection not found"
        )
    db.delete(error_injection)
    db.commit()
