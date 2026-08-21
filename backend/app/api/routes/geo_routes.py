import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.field import EntityField, FieldType
from app.models.geo_route import GeoRoute
from app.models.lookup_table import LookupTable
from app.models.user import User
from app.schemas.geo_route import GeoRouteCreate, GeoRouteRead
from app.services.geo_routes import GeoRouteError, validate_route_columns

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/geo-routes", tags=["geo-routes"]
)


@router.get("", response_model=list[GeoRouteRead])
def list_geo_routes(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeoRoute]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.geo_routes


@router.post("", response_model=GeoRouteRead, status_code=status.HTTP_201_CREATED)
def create_geo_route(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: GeoRouteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeoRoute:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_id does not belong to this entity",
        )
    if field.field_type not in (FieldType.OBJECT, FieldType.JSON):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geo routes can only be attached to object or json fields",
        )
    if any(g.field_id == payload.field_id for g in entity.geo_routes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This field already has a geo route attached",
        )

    lookup_table = db.get(LookupTable, payload.lookup_table_id)
    if lookup_table is None or lookup_table.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lookup_table_id does not belong to this project",
        )
    for column in (payload.lat_column, payload.lon_column):
        if column not in lookup_table.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{column}' is not a column of this lookup table",
            )

    try:
        validate_route_columns(lookup_table.data, payload.lat_column, payload.lon_column)
    except GeoRouteError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    geo_route = GeoRoute(
        entity_id=entity_id,
        field_id=payload.field_id,
        lookup_table_id=payload.lookup_table_id,
        lat_column=payload.lat_column,
        lon_column=payload.lon_column,
    )
    db.add(geo_route)
    db.commit()
    db.refresh(geo_route)
    return geo_route


@router.delete("/{geo_route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_geo_route(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    geo_route_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    geo_route = db.get(GeoRoute, geo_route_id)
    if geo_route is None or geo_route.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geo route not found")
    db.delete(geo_route)
    db.commit()
