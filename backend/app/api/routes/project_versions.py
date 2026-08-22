import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.db.session import get_db
from app.models.organization import Role
from app.models.project_version import ProjectVersion
from app.models.user import User
from app.schemas.project_version import (
    RollbackRequest,
    RollbackResult,
    VersionCreate,
    VersionDetail,
    VersionDiff,
    VersionRead,
)
from app.services import project_versions
from app.services.templates import restore_project

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["project versions"])


@router.get("", response_model=list[VersionRead])
def list_versions(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectVersion]:
    """Newest first. Metadata only — a list of twenty versions should not
    ship twenty full project designs to render twenty rows."""
    _get_owned_project(project_id, current_user, db)
    return list(
        db.scalars(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version.desc())
        ).all()
    )


@router.post("", response_model=VersionRead, status_code=status.HTTP_201_CREATED)
def create_version(
    project_id: uuid.UUID,
    payload: VersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectVersion:
    """Snapshot the design as it stands.

    Explicit rather than automatic. Recording a version on every mutation
    sounds thorough and produces a history nobody can read: fifty entries
    for one afternoon's editing, forty-nine of them a field half-renamed.
    """
    project = _get_owned_project(project_id, current_user, db, Role.MEMBER)
    version = project_versions.snapshot(db, project, current_user, payload.label)
    db.commit()
    db.refresh(version)
    return version


@router.get("/{version}", response_model=VersionDetail)
def get_version(
    project_id: uuid.UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectVersion:
    project = _get_owned_project(project_id, current_user, db)
    try:
        return project_versions.get(db, project, version)
    except project_versions.VersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{version}/diff", response_model=VersionDiff)
def diff_version(
    project_id: uuid.UUID,
    version: int,
    against: int | None = Query(
        default=None,
        description="Another version to compare with. Omitted, compares against the project "
        "as it stands now — which is the question people actually ask.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionDiff:
    """What changed between two versions, or between a version and now.

    Comparing against the live project is the default because "what have I
    changed since I saved this" is the question people actually ask; two
    stored versions is the rarer one.
    """
    project = _get_owned_project(project_id, current_user, db)
    try:
        source = project_versions.get(db, project, version)
        if against is None:
            from app.services.templates import export_project

            target_template = export_project(project, db).model_dump(mode="json")
            target_number = 0
        else:
            target = project_versions.get(db, project, against)
            target_template = target.template
            target_number = target.version
    except project_versions.VersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    result = project_versions.diff(source.template, target_template)
    return VersionDiff(
        from_version=source.version,
        to_version=target_number,
        identical=project_versions.is_empty(result),
        **result,
    )


@router.post("/{version}/rollback", response_model=RollbackResult)
def rollback(
    project_id: uuid.UUID,
    version: int,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RollbackResult:
    """Restore the project's design to a version.

    **The current state is snapshotted first**, always, and its number comes
    back in the response. Rolling back is the one moment you most want a way
    back, and asking someone to have remembered to snapshot beforehand is
    asking them to have predicted their own mistake.

    A rollback rebuilds every entity, and a record store hangs off an entity
    with `ON DELETE CASCADE` — so populated stores would go with it. That is
    refused unless the caller says explicitly that they know, because losing
    a generated population as a side effect of reverting a schema is not
    something to discover afterwards.
    """
    project = _get_owned_project(project_id, current_user, db, Role.MEMBER)
    try:
        target = project_versions.get(db, project, version)
    except project_versions.VersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not payload.discard_record_stores:
        at_risk = project_versions.record_stores_at_risk(db, project)
        if at_risk:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Rolling back rebuilds every entity, which would delete the stored "
                    f"records on {', '.join(at_risk)}. Send discard_record_stores=true "
                    "if that is what you want."
                ),
            )

    backup = project_versions.snapshot(
        db, project, current_user, label=f"before rollback to v{version}"
    )
    backup_number = backup.version

    try:
        restore_project(project, project_versions.template_of(target), db)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RollbackResult(restored_from=version, backup_version=backup_number)


@router.delete("/{version}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(
    project_id: uuid.UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a snapshot.

    The number is not reused: the next snapshot is still `max + 1`, so a
    version somebody referred to in a message last week cannot come back
    meaning something else.
    """
    project = _get_owned_project(project_id, current_user, db, Role.MEMBER)
    try:
        row = project_versions.get(db, project, version)
    except project_versions.VersionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.delete(row)
    db.commit()
