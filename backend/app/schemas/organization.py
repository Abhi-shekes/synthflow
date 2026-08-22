import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.organization import Role


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    # The caller's own role, not a list of everyone's. A UI needs to know
    # which buttons to show, and shipping the whole membership list on every
    # organisation read would leak who else is in it to a viewer who has no
    # business knowing.
    my_role: Role


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: Role
    created_at: datetime


class MemberInvite(BaseModel):
    """Membership is by email, not user id.

    The person adding someone knows their email address; they do not know a
    UUID, and making them find one first turns a two-second action into a
    support request.
    """

    email: EmailStr
    role: Role = Role.MEMBER


class MemberUpdate(BaseModel):
    role: Role


class ProjectOrganizationUpdate(BaseModel):
    """Move a project into an organisation, or back out of one.

    Null means personal again. Kept as an explicit action rather than a
    field on project update, because sharing a project with a group of
    people is not the same kind of change as renaming it.
    """

    organization_id: uuid.UUID | None
