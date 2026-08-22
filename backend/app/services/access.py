"""Who may do what to a project.

Before organisations, "may I touch this project" was `project.owner_id ==
user.id`, written out in two helper functions that 118 route call sites go
through. Those two helpers are the whole extension point: everything here
sits behind them, and no route changed.

**Write permission is decided by HTTP method, not by an argument threaded
through those 118 call sites.** That is the same rule the read-only API key
scope uses, for the same reason: a per-route list of "this one writes" is a
thing you forget to update when you add a route, and forgetting there means
a viewer who can write. The method is stashed on a context variable by
`deps.get_current_user`, which already receives the request and already runs
on every authenticated route.

A context variable rather than a parameter because contextvars are
per-task — under asyncio each request is its own task, so two concurrent
requests cannot see each other's method. A module-level global would be a
race; passing it explicitly would be 118 edits.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.organization import OrganizationMember, Role
from app.models.project import Project
from app.models.user import User

# Set per request by `deps.get_current_user`. The default matters: code
# reached outside a request — a job worker, a test calling a service
# directly — must not be treated as a mutation it never made, and GET is the
# reading that grants the least.
current_method: ContextVar[str] = ContextVar("current_method", default="GET")

# GET, HEAD and OPTIONS change nothing. Identical to the API-key rule, and
# deliberately the same set: two different definitions of "a write" would
# eventually disagree.
READING_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def role_for(db: Session, project: Project, user: User) -> Role | None:
    """This user's role on this project, or None if they have none.

    The owner is always OWNER, whatever the organisation says. Moving a
    project into an organisation must not be a way to lock its owner out of
    it, and an owner who joined their own org as a viewer would otherwise be
    exactly that.
    """
    if project.owner_id == user.id:
        return Role.OWNER
    if project.organization_id is None:
        return None
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    return membership.role if membership else None


def may(db: Session, project: Project, user: User, needed: Role = Role.VIEWER) -> bool:
    role = role_for(db, project, user)
    if role is None:
        return False
    if not role.allows(needed):
        return False
    if current_method.get() not in READING_METHODS and not role.allows(Role.MEMBER):
        return False
    return True


def visible_projects(user: User):
    """A filter for "projects this user can see".

    Owned, or belonging to an organisation they are a member of. Written as
    a subquery rather than two queries and a merge so ordering and paging
    stay the database's job.
    """
    member_orgs = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user.id
    )
    return or_(
        Project.owner_id == user.id,
        Project.organization_id.in_(member_orgs),
    )


def org_role(db: Session, organization_id: uuid.UUID, user: User) -> Role | None:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    return membership.role if membership else None
