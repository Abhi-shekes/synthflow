import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.database_connection import DatabaseConnection
from app.models.object_storage import ObjectStorageTarget
from app.models.project import Project
from app.models.user import User
from app.schemas.template import ProjectTemplate
from app.services import ingest
from app.services.profiling.profile import ProfileError, profile_files, profile_tables

router = APIRouter(prefix="/profile", tags=["profiling"])


class ColumnReport(BaseModel):
    """What was learned about one column, so the UI can show the reasoning
    rather than just the resulting formula."""

    entity: str
    column: str
    field: str
    type: str
    rows: int
    missing: int
    distinct: int
    distribution: str | None = None
    fit_quality: str | None = None
    categories: int | None = None
    # Phase 10. `pii_kind` is what the column appears to hold, `pii_redacted`
    # is whether that was acted on — the two differ for a MEDIUM-confidence
    # finding, which is reported for a human to judge but left alone.
    pii_kind: str | None = None
    pii_confidence: str | None = None
    pii_redacted: bool = False
    pii_reason: str | None = None


class ProfileResponse(BaseModel):
    """Same shape as schema import: a template plus what couldn't be
    carried across. Nothing is created until the template is applied via
    `POST /projects/import` — see app.services.schema_import.common for
    why that split is structural rather than a UI convention."""

    template: ProjectTemplate
    warnings: list[str] = Field(default_factory=list)
    report: list[ColumnReport] = Field(default_factory=list)


@router.post("", response_model=ProfileResponse)
async def profile_sample(
    files: list[UploadFile] = File(...),
    project_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """Learn a project from one or more sample files.

    Multiple files are profiled together on purpose: that's what makes
    detecting relationships between them possible, which a
    one-file-at-a-time endpoint couldn't do.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one file"
        )

    payloads = [(f.filename or "sample.csv", await f.read()) for f in files]

    try:
        result, profiles_by_entity = profile_files(
            payloads,
            max_rows=settings.MAX_PROFILE_ROWS,
            project_name=project_name,
        )
    except ProfileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _response(result, profiles_by_entity)


def _response(result, profiles_by_entity) -> ProfileResponse:
    """Turn a profiling result into the API shape. Shared by every
    source so a URL, an object and an upload cannot drift apart in what
    they report."""
    report: list[ColumnReport] = []
    for entity in result.template.entities:
        fields_by_name = {f.name: f for f in entity.fields}
        for profile in profiles_by_entity[entity.name]:
            field = fields_by_name.get(profile.field_name)
            report.append(
                ColumnReport(
                    entity=entity.name,
                    column=profile.name,
                    field=profile.field_name,
                    type=profile.inferred_type,
                    rows=profile.total,
                    missing=profile.missing,
                    distinct=profile.distinct,
                    distribution=(field.formula if field is not None else None)
                    or (profile.fit.kind if profile.fit else None),
                    fit_quality=profile.fit.quality if profile.fit else None,
                    categories=len(profile.categories) if profile.categories else None,
                    pii_kind=profile.pii.kind.value if profile.pii else None,
                    pii_confidence=profile.pii.confidence.value if profile.pii else None,
                    pii_redacted=profile.redacted,
                    pii_reason=profile.pii.reason if profile.pii else None,
                )
            )

    return ProfileResponse(template=result.template, warnings=result.warnings, report=report)


class ProfileSourceRequest(BaseModel):
    """Learn from data SynthFlow can fetch itself, rather than an upload.

    Exactly one of `urls`, `object_keys` or `tables` is expected. They are
    separate fields rather than one polymorphic list because each needs
    different companions — object keys need a storage target, tables need a
    database connection — and a single field would have made those
    conditionally-required, which is a validation rule nobody can see from
    the schema.
    """

    # Optional, and only optional for URLs. Object keys and tables need
    # credentials that belong to a project; a public URL needs nothing, and
    # requiring a project for it would mean you could not learn from one
    # until you had already made a project to learn into.
    project_id: uuid.UUID | None = None
    project_name: str | None = None
    urls: list[str] = Field(default_factory=list)
    storage_target_id: uuid.UUID | None = None
    object_keys: list[str] = Field(default_factory=list)
    connection_id: uuid.UUID | None = None
    tables: list[str] = Field(default_factory=list)


def _owned_project(project_id: uuid.UUID, user: User, db: Session) -> Project:
    """Delegates rather than repeating the ownership test.

    This was a third copy of `project.owner_id != user.id`. Organisations
    made that a liability: three copies of an access rule are three places
    to update and two of them will be missed. There is one rule now, in
    `projects._get_owned_project`.
    """
    return _get_owned_project(project_id, user, db)


@router.post("/from-source", response_model=ProfileResponse)
def profile_from_source(
    payload: ProfileSourceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Learn a project from a URL, an object-storage key, or a database table.

    Scoped to a project because two of the three sources need credentials
    that belong to one — a storage target or a database connection. The
    result is still just a template: like every other importer, nothing is
    created until it is applied.
    """
    project_id = payload.project_id
    if project_id is not None:
        _owned_project(project_id, current_user, db)

    chosen = [bool(payload.urls), bool(payload.object_keys), bool(payload.tables)]
    if sum(chosen) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Give exactly one of urls, object_keys or tables",
        )

    max_rows = settings.MAX_PROFILE_ROWS
    try:
        if payload.tables:
            if project_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="project_id is required when reading tables",
                )
            connection = _connection(payload.connection_id, project_id, db)
            tables = []
            for table in payload.tables:
                columns, rows = ingest.read_table(connection, table, max_rows)
                tables.append((table, columns, rows))
            result, profiles = profile_tables(
                tables, project_name=payload.project_name, source_label="table"
            )
        else:
            if payload.urls:
                files = [ingest.fetch_url(url) for url in payload.urls]
            else:
                if project_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="project_id is required when reading object keys",
                    )
                target = _storage_target(payload.storage_target_id, project_id, db)
                files = [ingest.fetch_object(target, key) for key in payload.object_keys]
            result, profiles = profile_files(
                files, max_rows=max_rows, project_name=payload.project_name
            )
    except (ProfileError, ingest.IngestError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _response(result, profiles)


@router.get("/objects", response_model=list[str])
def list_source_objects(
    project_id: uuid.UUID,
    storage_target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Keys available under a storage target, so the UI can offer a list
    rather than asking someone to remember an object key."""
    _owned_project(project_id, current_user, db)
    target = _storage_target(storage_target_id, project_id, db)
    try:
        return ingest.list_objects(target)
    except ingest.IngestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _storage_target(
    target_id: uuid.UUID | None, project_id: uuid.UUID, db: Session
) -> ObjectStorageTarget:
    if target_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_target_id is required when reading object keys",
        )
    target = db.get(ObjectStorageTarget, target_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage target not found"
        )
    return target


def _connection(
    connection_id: uuid.UUID | None, project_id: uuid.UUID, db: Session
) -> DatabaseConnection:
    if connection_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connection_id is required when reading tables",
        )
    connection = db.get(DatabaseConnection, connection_id)
    if connection is None or connection.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return connection
