import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.organization import Role
from app.models.project import Project
from app.models.user import User
from app.schemas.organization import ProjectOrganizationUpdate
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import access

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_owned_project(
    project_id: uuid.UUID, user: User, db: Session, needed: Role = Role.VIEWER
) -> Project:
    """The project, if this user may act on it.

    One of the two functions every project-scoped route goes through, which
    is why organisations needed no route changes: the rule moved, the call
    sites did not.

    **A project the caller cannot see is a 404, not a 403.** Telling someone
    a project exists but is not theirs is telling them something they had no
    right to learn. A 403 is reserved for the case where they *can* see it
    and the role is not enough — there, hiding it would be confusing rather
    than protective.
    """
    project = db.get(Project, project_id)
    if project is None or access.role_for(db, project, user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not access.may(db, project, user, needed):
        role = access.role_for(db, project, user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role on this project is {role} — that is not enough to do this",
        )
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Project]:
    # Owned, plus anything belonging to an organisation this user is in.
    return (
        db.query(Project)
        .filter(access.visible_projects(current_user))
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    return _get_owned_project(project_id, current_user, db)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = _get_owned_project(project_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    project = _get_owned_project(project_id, current_user, db)
    db.delete(project)
    db.commit()


@router.put("/{project_id}/organization", response_model=ProjectRead)
def set_project_organization(
    project_id: uuid.UUID,
    payload: ProjectOrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    """Share a project with an organisation, or take it back.

    Only the project's **owner** may do this, not an org admin. Sharing your
    work with a group is a decision about your work; an admin who could move
    projects in and out of their organisation could quietly take one over.

    Moving into an organisation requires being a member of it at MEMBER or
    above — you cannot hand a project to a group you only read for, and you
    certainly cannot hand it to one you are not in.
    """
    project = db.get(Project, project_id)
    if project is None or access.role_for(db, project, current_user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project's owner can change which organization it belongs to",
        )

    if payload.organization_id is not None:
        role = access.org_role(db, payload.organization_id, current_user)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        if not role.allows(Role.MEMBER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"You are a {role} of that organization — that is not enough to share into it"
                ),
            )

    project.organization_id = payload.organization_id
    db.commit()
    db.refresh(project)
    return project
