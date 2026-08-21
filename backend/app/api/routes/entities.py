import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.entity import Entity
from app.models.field import EntityField, FieldType
from app.models.relationship import Relationship
from app.models.user import User
from app.schemas.entity import EntityCreate, EntityRead, EntityUpdate, GenerateRequest
from app.schemas.field import EntityFieldCreate, EntityFieldRead, EntityFieldUpdate
from app.services.expressions import ExpressionError, evaluate
from app.services.field_validation import validate_enum_weights, validate_preset
from app.services.generator import build_lookup_pools, generate_rows, rows_to_csv, rows_to_excel

router = APIRouter(prefix="/projects/{project_id}/entities", tags=["entities"])

_DUMMY_UUID = "00000000-0000-0000-0000-000000000000"


def _dummy_value_for_field(field: EntityField) -> object:
    """A type-appropriate stand-in for a field's real generated value,
    used only for validating a formula/rule/event-trigger condition at
    creation time (see dummy_row_values below) — close enough to what a
    real row will contain that a condition calling a type-specific
    function (a plugin's `is_business_day(order_date)`, say) validates
    successfully instead of being rejected just because a DATE field's
    stand-in used to always be the integer 1 regardless of its real
    type."""
    if field.field_type == FieldType.ENUM:
        return field.enum_values[0] if field.enum_values else "x"
    if field.field_type == FieldType.STRING:
        return "x"
    if field.field_type == FieldType.BOOLEAN:
        return True
    if field.field_type == FieldType.DATE:
        return date.today().isoformat()
    if field.field_type == FieldType.DATETIME:
        return datetime.now().isoformat()
    if field.field_type == FieldType.UUID:
        return _DUMMY_UUID
    if field.field_type == FieldType.ARRAY:
        return []
    if field.field_type in (FieldType.OBJECT, FieldType.JSON):
        return {}
    return 1


def dummy_row_values(entity: Entity, db: Session) -> dict[str, object]:
    """Dummy values for validating a formula/rule/event-trigger condition at
    creation time: a type-appropriate stand-in for each of the entity's
    own fields (see _dummy_value_for_field), plus a nested dummy dict per
    related entity (keyed by that entity's *name*) for any Relationship
    sourced from this entity. This is what lets a formula or condition
    reference `TargetEntity.field` (see app.services.expressions and
    app.services.generator's relationship_lookup/cross-entity handling)
    validate before ever generating data — shared by rules.py and
    event_triggers.py, not just formula validation here, since all three
    use the same evaluator and the same cross-entity mechanism."""
    values: dict[str, object] = {f.name: _dummy_value_for_field(f) for f in entity.fields}
    relationships = db.query(Relationship).filter(Relationship.source_entity_id == entity.id).all()
    for rel in relationships:
        target_entity = db.get(Entity, rel.target_entity_id)
        if target_entity is not None:
            values[target_entity.name] = {
                f.name: _dummy_value_for_field(f) for f in target_entity.fields
            }
    return values


def _get_owned_entity(
    project_id: uuid.UUID, entity_id: uuid.UUID, user: User, db: Session
) -> Entity:
    _get_owned_project(project_id, user, db)
    entity = db.get(Entity, entity_id)
    if entity is None or entity.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity


@router.get("", response_model=list[EntityRead])
def list_entities(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Entity]:
    _get_owned_project(project_id, current_user, db)
    return db.query(Entity).filter(Entity.project_id == project_id).all()


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(
    project_id: uuid.UUID,
    payload: EntityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Entity:
    _get_owned_project(project_id, current_user, db)
    entity = Entity(project_id=project_id, name=payload.name)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.get("/{entity_id}", response_model=EntityRead)
def get_entity(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Entity:
    return _get_owned_entity(project_id, entity_id, current_user, db)


@router.patch("/{entity_id}", response_model=EntityRead)
def update_entity(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: EntityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Entity:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    db.delete(entity)
    db.commit()


@router.post(
    "/{entity_id}/fields", response_model=EntityFieldRead, status_code=status.HTTP_201_CREATED
)
def add_field(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: EntityFieldCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityField:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    if payload.formula:
        try:
            evaluate(payload.formula, dummy_row_values(entity, db))
        except ExpressionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        validate_enum_weights(payload.field_type, payload.enum_values, payload.enum_weights)
        validate_preset(payload.field_type, payload.preset, payload.regex)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    field = EntityField(entity_id=entity_id, **payload.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.patch("/{entity_id}/fields/{field_id}", response_model=EntityFieldRead)
def update_field(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: EntityFieldUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityField:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    field = db.get(EntityField, field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("formula"):
        try:
            evaluate(updates["formula"], dummy_row_values(entity, db))
        except ExpressionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        validate_enum_weights(
            updates.get("field_type", field.field_type),
            updates.get("enum_values", field.enum_values),
            updates.get("enum_weights", field.enum_weights),
        )
        validate_preset(
            updates.get("field_type", field.field_type),
            updates.get("preset", field.preset),
            updates.get("regex", field.regex),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    for attr, value in updates.items():
        setattr(field, attr, value)
    db.commit()
    db.refresh(field)
    return field


@router.delete("/{entity_id}/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    field = db.get(EntityField, field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    db.delete(field)
    db.commit()


@router.post("/{entity_id}/generate", response_model=None)
def generate(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: GenerateRequest,
    format: Literal["json", "csv", "xlsx"] = "json",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict] | Response:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    if payload.count < 1 or payload.count > settings.MAX_GENERATE_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"count must be between 1 and {settings.MAX_GENERATE_ROWS}",
        )
    try:
        rows = generate_rows(
            entity.fields,
            payload.count,
            fk_pools=build_lookup_pools(entity.lookup_attachments),
            rules=entity.rules,
            workflows=entity.workflows,
            trends=entity.trends,
            error_injections=entity.error_injections,
            event_triggers=entity.event_triggers,
            geo_routes=entity.geo_routes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if format == "csv":
        csv_text = rows_to_csv(entity.fields, rows)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{entity.name}.csv"'},
        )

    if format == "xlsx":
        xlsx_bytes = rows_to_excel(entity.fields, rows)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{entity.name}.xlsx"'},
        )

    return rows
