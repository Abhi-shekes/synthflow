import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember, Role
from app.models.project import Project
from app.models.user import User
from app.schemas.organization import (
    MemberInvite,
    MemberRead,
    MemberUpdate,
    OrganizationCreate,
    OrganizationRead,
)
from app.services import access

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _membership(
    organization_id: uuid.UUID, user: User, db: Session, needed: Role = Role.VIEWER
) -> Organization:
    """The organisation, if this user is in it at a sufficient role.

    Not being a member is a 404 for the same reason a project you cannot see
    is: telling someone an organisation exists but excludes them is telling
    them something they had no right to learn. Being a member at too low a
    role is a 403, because there hiding it would confuse rather than
    protect.
    """
    organization = db.get(Organization, organization_id)
    role = access.org_role(db, organization_id, user) if organization else None
    if organization is None or role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not role.allows(needed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are a {role} of this organization — that is not enough to do this",
        )
    return organization


def _read(db: Session, organization: Organization, user: User) -> OrganizationRead:
    role = access.org_role(db, organization.id, user)
    return OrganizationRead(
        id=organization.id,
        name=organization.name,
        created_at=organization.created_at,
        my_role=role or Role.VIEWER,
    )


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrganizationRead]:
    """Organisations this user belongs to. There is no listing of all of
    them — an organisation you are not in is not yours to know about."""
    organizations = db.scalars(
        select(Organization)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(Organization.created_at)
    ).all()
    return [_read(db, org, current_user) for org in organizations]


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationRead:
    """Create an organisation. The creator becomes its owner in the same
    transaction — an organisation with no owner is one nobody can administer
    and nobody can delete."""
    organization = Organization(name=payload.name)
    db.add(organization)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=organization.id, user_id=current_user.id, role=Role.OWNER
        )
    )
    db.commit()
    db.refresh(organization)
    return _read(db, organization, current_user)


@router.get("/{organization_id}/members", response_model=list[MemberRead])
def list_members(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberRead]:
    organization = _membership(organization_id, current_user, db)
    return [
        MemberRead(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            role=m.role,
            created_at=m.created_at,
        )
        for m in sorted(organization.members, key=lambda m: m.created_at)
    ]


@router.post("/{organization_id}/members", response_model=MemberRead, status_code=201)
def add_member(
    organization_id: uuid.UUID,
    payload: MemberInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberRead:
    """Add someone by email, at a role no higher than your own.

    That last rule is the one worth stating: an admin who could mint an
    owner could promote themselves through a second account, which makes the
    ladder decorative.
    """
    _membership(organization_id, current_user, db, Role.ADMIN)
    actor_role = access.org_role(db, organization_id, current_user)
    if actor_role is None or not actor_role.allows(payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant {payload.role} — it is above your own role",
        )

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        # Deliberately explicit. This is not a login form: hiding whether an
        # account exists here would leave an admin unable to tell a typo
        # from someone who has not signed up.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account for {payload.email} — they need to sign up first",
        )
    if access.org_role(db, organization_id, user) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That person is already a member",
        )

    member = OrganizationMember(organization_id=organization_id, user_id=user.id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return MemberRead(
        id=member.id,
        user_id=member.user_id,
        email=user.email,
        role=member.role,
        created_at=member.created_at,
    )


def _get_member(
    organization_id: uuid.UUID, member_id: uuid.UUID, db: Session
) -> OrganizationMember:
    member = db.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


def _refuse_last_owner(db: Session, member: OrganizationMember) -> None:
    """An organisation must keep at least one owner.

    Without this, the last owner can demote or remove themselves and leave
    an organisation nobody can administer, delete, or add members to — a
    row that exists forever with no way back in.
    """
    if member.role != Role.OWNER:
        return
    owners = [m for m in member.organization.members if m.role == Role.OWNER]
    if len(owners) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This is the last owner. Promote someone else first, or the organization "
                "would be left with nobody who can administer it."
            ),
        )


@router.patch("/{organization_id}/members/{member_id}", response_model=MemberRead)
def update_member(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberRead:
    _membership(organization_id, current_user, db, Role.ADMIN)
    actor_role = access.org_role(db, organization_id, current_user)
    member = _get_member(organization_id, member_id, db)

    if actor_role is None or not actor_role.allows(payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant {payload.role} — it is above your own role",
        )
    if not actor_role.allows(member.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot change a {member.role} — they outrank you",
        )
    _refuse_last_owner(db, member)

    member.role = payload.role
    db.commit()
    db.refresh(member)
    return MemberRead(
        id=member.id,
        user_id=member.user_id,
        email=member.user.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{organization_id}/members/{member_id}", status_code=204)
def remove_member(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _membership(organization_id, current_user, db, Role.ADMIN)
    actor_role = access.org_role(db, organization_id, current_user)
    member = _get_member(organization_id, member_id, db)

    if actor_role is None or not actor_role.allows(member.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot remove a {member.role} — they outrank you",
        )
    _refuse_last_owner(db, member)

    db.delete(member)
    db.commit()


@router.delete("/{organization_id}", status_code=204)
def delete_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Dissolve an organisation.

    Its projects are *not* deleted — `Project.organization_id` is
    `ON DELETE SET NULL`, so they return to their owners as personal
    projects. Destroying other people's work as a side effect of tidying up
    a group would be a spectacular way to lose data.
    """
    organization = _membership(organization_id, current_user, db, Role.OWNER)

    # Detached explicitly rather than left to the foreign key's SET NULL.
    # The constraint is real and does the same thing on Postgres, but SQLite
    # does not enforce foreign keys unless asked to, so relying on it alone
    # meant the behaviour was only true in production and untested anywhere.
    # Being explicit also puts the intent where someone reading this route
    # will see it.
    for project in db.scalars(
        select(Project).where(Project.organization_id == organization_id)
    ).all():
        project.organization_id = None

    db.delete(organization)
    db.commit()
