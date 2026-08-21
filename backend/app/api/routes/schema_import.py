import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.database_connection import DatabaseConnection
from app.models.user import User
from app.schemas.template import ProjectTemplate
from app.services.db_output import DatabaseOutputError
from app.services.schema_import import (
    JSONSchemaImportError,
    SampleImportError,
    SQLImportError,
    import_from_database,
    import_from_json_schema,
    import_from_sample,
    import_from_sql,
)

router = APIRouter(prefix="/schema-import", tags=["schema-import"])


class SchemaImportResponse(BaseModel):
    """Deliberately *not* a created project.

    Every importer returns a template plus what it couldn't carry across;
    applying it is a separate `POST /projects/import` call. That keeps the
    review step structural rather than something a UI could skip, and
    reuses the import path that already validates and applies
    all-or-nothing — see app.services.schema_import.common.
    """

    template: ProjectTemplate
    warnings: list[str] = Field(default_factory=list)


class DatabaseImportRequest(BaseModel):
    connection_id: uuid.UUID
    project_name: str | None = None
    schema_name: str | None = None


class SQLImportRequest(BaseModel):
    sql: str
    dialect: str | None = None
    project_name: str | None = None


class JSONSchemaImportRequest(BaseModel):
    document: dict
    project_name: str | None = None


@router.post("/database", response_model=SchemaImportResponse)
def import_database_schema(
    payload: DatabaseImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchemaImportResponse:
    """Introspect a saved DatabaseConnection into a template.

    Reuses the project's existing connection record rather than taking
    credentials in the request body, so importing and pushing share one
    place where a password lives.
    """
    connection = db.get(DatabaseConnection, payload.connection_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found"
        )
    _get_owned_project(connection.project_id, current_user, db)

    try:
        result = import_from_database(
            connection,
            project_name=payload.project_name,
            schema=payload.schema_name,
        )
    except DatabaseOutputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SchemaImportResponse(template=result.template, warnings=result.warnings)


@router.post("/sql", response_model=SchemaImportResponse)
def import_sql_schema(
    payload: SQLImportRequest,
    current_user: User = Depends(get_current_user),
) -> SchemaImportResponse:
    try:
        result = import_from_sql(
            payload.sql, dialect=payload.dialect, project_name=payload.project_name
        )
    except SQLImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SchemaImportResponse(template=result.template, warnings=result.warnings)


@router.post("/json-schema", response_model=SchemaImportResponse)
def import_json_schema(
    payload: JSONSchemaImportRequest,
    current_user: User = Depends(get_current_user),
) -> SchemaImportResponse:
    """Handles both JSON Schema and OpenAPI — an OpenAPI document's
    `components.schemas` are JSON Schema, so they share one importer."""
    try:
        result = import_from_json_schema(payload.document, project_name=payload.project_name)
    except JSONSchemaImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SchemaImportResponse(template=result.template, warnings=result.warnings)


@router.post("/sample", response_model=SchemaImportResponse)
async def import_sample_file(
    file: UploadFile = File(...),
    project_name: str | None = Form(None),
    entity_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> SchemaImportResponse:
    content = await file.read()
    try:
        result = import_from_sample(
            file.filename or "sample.csv",
            content,
            max_rows=settings.MAX_LOOKUP_ROWS,
            entity_name=entity_name,
            project_name=project_name,
        )
    except SampleImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SchemaImportResponse(template=result.template, warnings=result.warnings)


@router.post("/openapi-file", response_model=SchemaImportResponse)
async def import_openapi_file(
    file: UploadFile = File(...),
    project_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> SchemaImportResponse:
    """Same importer as /json-schema, but for an uploaded file rather than
    an inlined document — OpenAPI specs are usually too large to paste."""
    content = await file.read()
    try:
        document = json.loads(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That file isn't valid JSON: {exc}",
        ) from exc

    try:
        result = import_from_json_schema(document, project_name=project_name)
    except JSONSchemaImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SchemaImportResponse(template=result.template, warnings=result.warnings)
