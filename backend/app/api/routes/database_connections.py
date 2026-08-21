import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.database_connection import DatabaseConnection
from app.models.user import User
from app.schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionRead,
    DatabaseConnectionTestResult,
    DatabasePushRequest,
    DatabasePushResult,
)
from app.services import metrics
from app.services.db_output import DatabaseOutputError, push_rows, test_connection
from app.services.generator import build_lookup_pools, generate_rows

router = APIRouter(
    prefix="/projects/{project_id}/database-connections", tags=["database-connections"]
)


def _get_owned_connection(
    project_id: uuid.UUID, connection_id: uuid.UUID, user: User, db: Session
) -> DatabaseConnection:
    _get_owned_project(project_id, user, db)
    connection = db.get(DatabaseConnection, connection_id)
    if connection is None or connection.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found"
        )
    return connection


@router.get("", response_model=list[DatabaseConnectionRead])
def list_connections(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DatabaseConnection]:
    _get_owned_project(project_id, current_user, db)
    return db.query(DatabaseConnection).filter(DatabaseConnection.project_id == project_id).all()


@router.post("", response_model=DatabaseConnectionRead, status_code=status.HTTP_201_CREATED)
def create_connection(
    project_id: uuid.UUID,
    payload: DatabaseConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseConnection:
    _get_owned_project(project_id, current_user, db)
    connection = DatabaseConnection(project_id=project_id, **payload.model_dump())
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    connection = _get_owned_connection(project_id, connection_id, current_user, db)
    db.delete(connection)
    db.commit()


@router.post("/{connection_id}/test", response_model=DatabaseConnectionTestResult)
def test(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseConnectionTestResult:
    connection = _get_owned_connection(project_id, connection_id, current_user, db)
    ok, detail = test_connection(connection)
    return DatabaseConnectionTestResult(ok=ok, detail=detail)


@router.post("/{connection_id}/push", response_model=DatabasePushResult)
def push(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    payload: DatabasePushRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabasePushResult:
    connection = _get_owned_connection(project_id, connection_id, current_user, db)
    entity = _get_owned_entity(project_id, payload.entity_id, current_user, db)

    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    if payload.count < 1 or payload.count > settings.MAX_GENERATE_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"count must be between 1 and {settings.MAX_GENERATE_ROWS}",
        )

    table_name = payload.table_name or entity.name.lower().replace(" ", "_")

    try:
        with metrics.generation("database_push") as recorder:
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
            recorder.count(len(rows))
        rows_written = push_rows(connection, entity.fields, rows, table_name)
    except (ValueError, DatabaseOutputError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DatabasePushResult(table=table_name, rows_written=rows_written)
