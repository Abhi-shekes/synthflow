import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.entity import Entity
from app.models.field import EntityField
from app.models.relationship import Relationship
from app.models.user import User
from app.schemas.relationship import (
    ProjectGenerateRequest,
    RelationshipCreate,
    RelationshipRead,
)
from app.services.generator import generate_project, project_rows_to_csv_zip, project_rows_to_excel

router = APIRouter(prefix="/projects/{project_id}", tags=["relationships"])


def _get_field_in_entity(
    db: Session, entity_id: uuid.UUID, field_id: uuid.UUID, role: str
) -> EntityField:
    field = db.get(EntityField, field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{role}_field_id does not belong to {role}_entity_id",
        )
    return field


@router.get("/relationships", response_model=list[RelationshipRead])
def list_relationships(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Relationship]:
    _get_owned_project(project_id, current_user, db)
    return db.query(Relationship).filter(Relationship.project_id == project_id).all()


@router.post(
    "/relationships", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED
)
def create_relationship(
    project_id: uuid.UUID,
    payload: RelationshipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Relationship:
    _get_owned_project(project_id, current_user, db)

    if payload.source_entity_id == payload.target_entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A relationship must connect two different entities",
        )

    for entity_id, label in (
        (payload.source_entity_id, "source"),
        (payload.target_entity_id, "target"),
    ):
        entity = db.get(Entity, entity_id)
        if entity is None or entity.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label}_entity_id does not belong to this project",
            )

    source_field = _get_field_in_entity(
        db, payload.source_entity_id, payload.source_field_id, "source"
    )
    target_field = _get_field_in_entity(
        db, payload.target_entity_id, payload.target_field_id, "target"
    )

    if source_field.field_type != target_field.field_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"source field type ({source_field.field_type}) must match "
                f"target field type ({target_field.field_type})"
            ),
        )

    relationship = Relationship(project_id=project_id, **payload.model_dump())
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    project_id: uuid.UUID,
    relationship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    relationship = db.get(Relationship, relationship_id)
    if relationship is None or relationship.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    db.delete(relationship)
    db.commit()


@router.post("/generate", response_model=None)
def generate_all(
    project_id: uuid.UUID,
    payload: ProjectGenerateRequest,
    format: Literal["json", "csv", "xlsx"] = "json",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]] | Response:
    """Generate every entity in the project at once, honoring relationships so a
    dependent entity's foreign-key field references its parent's generated rows."""
    project = _get_owned_project(project_id, current_user, db)
    entities = db.query(Entity).filter(Entity.project_id == project_id).all()
    if not entities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no entities to generate"
        )
    relationships = db.query(Relationship).filter(Relationship.project_id == project_id).all()

    counts: dict[uuid.UUID, int] = {}
    for entity in entities:
        count = payload.counts.get(entity.id, payload.count)
        if count < 1 or count > settings.MAX_GENERATE_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"count for '{entity.name}' must be between 1 and "
                    f"{settings.MAX_GENERATE_ROWS}"
                ),
            )
        counts[entity.id] = count

    try:
        generated = generate_project(entities, relationships, counts)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if format == "csv":
        zip_bytes = project_rows_to_csv_zip(entities, generated)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{project.name}.zip"'},
        )

    if format == "xlsx":
        xlsx_bytes = project_rows_to_excel(entities, generated)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{project.name}.xlsx"'},
        )

    entities_by_id = {e.id: e for e in entities}
    return {entities_by_id[entity_id].name: rows for entity_id, rows in generated.items()}
