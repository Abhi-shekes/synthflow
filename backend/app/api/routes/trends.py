import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.field import EntityField, FieldType
from app.models.trend import Trend
from app.models.user import User
from app.schemas.trend import TrendCreate, TrendRead
from app.services.trends import validate_params

router = APIRouter(prefix="/projects/{project_id}/entities/{entity_id}/trends", tags=["trends"])


@router.get("", response_model=list[TrendRead])
def list_trends(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Trend]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.trends


@router.post("", response_model=TrendRead, status_code=status.HTTP_201_CREATED)
def create_trend(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: TrendCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Trend:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_id does not belong to this entity",
        )
    if field.field_type not in (FieldType.INTEGER, FieldType.FLOAT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trends can only be attached to integer or float fields",
        )
    if any(t.field_id == payload.field_id for t in entity.trends):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This field already has a trend attached",
        )

    try:
        validate_params(payload.trend_type, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    trend = Trend(
        entity_id=entity_id,
        field_id=payload.field_id,
        trend_type=payload.trend_type,
        params=payload.params,
    )
    db.add(trend)
    db.commit()
    db.refresh(trend)
    return trend


@router.delete("/{trend_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trend(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    trend_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    trend = db.get(Trend, trend_id)
    if trend is None or trend.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trend not found")
    db.delete(trend)
    db.commit()
