import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project, get_db
from app.models.object_storage import ObjectStorageTarget
from app.models.project import Project
from app.models.user import User
from app.schemas.object_storage import (
    ObjectStorageTargetCreate,
    ObjectStorageTargetRead,
    ObjectStorageTestResult,
)
from app.services.object_storage import test_connection

router = APIRouter(prefix="/projects/{project_id}/storage-targets", tags=["object storage"])


def _owned_project(project_id: uuid.UUID, user: User, db: Session) -> Project:
    """Delegates rather than repeating the ownership test.

    This was a third copy of `project.owner_id != user.id`. Organisations
    made that a liability: three copies of an access rule are three places
    to update and two of them will be missed. There is one rule now, in
    `projects._get_owned_project`.
    """
    return _get_owned_project(project_id, user, db)


def _owned_target(
    project_id: uuid.UUID, target_id: uuid.UUID, user: User, db: Session
) -> ObjectStorageTarget:
    _owned_project(project_id, user, db)
    target = db.get(ObjectStorageTarget, target_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage target not found"
        )
    return target


@router.post("", response_model=ObjectStorageTargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    project_id: uuid.UUID,
    payload: ObjectStorageTargetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObjectStorageTarget:
    _owned_project(project_id, current_user, db)
    target = ObjectStorageTarget(project_id=project_id, **payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.get("", response_model=list[ObjectStorageTargetRead])
def list_targets(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ObjectStorageTarget]:
    _owned_project(project_id, current_user, db)
    return db.query(ObjectStorageTarget).filter(ObjectStorageTarget.project_id == project_id).all()


@router.post("/{target_id}/test", response_model=ObjectStorageTestResult)
def test_target(
    project_id: uuid.UUID,
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObjectStorageTestResult:
    """Check the bucket is reachable before a job depends on it.

    Failure is a 200 with `ok: false` rather than an error status: an
    unreachable bucket is a fact about the user's configuration, not a
    failure of this request. Same shape as the database connection test.
    """
    target = _owned_target(project_id, target_id, current_user, db)
    ok, detail = test_connection(target)
    return ObjectStorageTestResult(ok=ok, detail=detail)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    project_id: uuid.UUID,
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    target = _owned_target(project_id, target_id, current_user, db)
    db.delete(target)
    db.commit()
