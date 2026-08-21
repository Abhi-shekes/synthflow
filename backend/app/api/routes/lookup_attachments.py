import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.field import EntityField
from app.models.lookup_attachment import LookupAttachment
from app.models.lookup_table import LookupTable
from app.models.user import User
from app.schemas.lookup_attachment import LookupAttachmentCreate, LookupAttachmentRead

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/lookup-attachments",
    tags=["lookup-attachments"],
)


@router.get("", response_model=list[LookupAttachmentRead])
def list_lookup_attachments(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupAttachment]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.lookup_attachments


@router.post("", response_model=LookupAttachmentRead, status_code=status.HTTP_201_CREATED)
def create_lookup_attachment(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: LookupAttachmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LookupAttachment:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_id does not belong to this entity",
        )
    if any(a.field_id == payload.field_id for a in entity.lookup_attachments):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This field already has a lookup attached",
        )

    lookup_table = db.get(LookupTable, payload.lookup_table_id)
    if lookup_table is None or lookup_table.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lookup_table_id does not belong to this project",
        )
    if payload.column not in lookup_table.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{payload.column}' is not a column of this lookup table",
        )

    attachment = LookupAttachment(
        entity_id=entity_id,
        field_id=payload.field_id,
        lookup_table_id=payload.lookup_table_id,
        column=payload.column,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lookup_attachment(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    attachment = db.get(LookupAttachment, attachment_id)
    if attachment is None or attachment.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lookup attachment not found"
        )
    db.delete(attachment)
    db.commit()
