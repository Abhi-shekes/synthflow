import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    ui_mode: Literal["guided", "advanced"]
    has_onboarded: bool


class UserUpdate(BaseModel):
    """Both fields are user-set preferences, never inferred server-side —
    onboarding completion is recorded when the welcome flow finishes or is
    skipped, not guessed from activity."""

    ui_mode: Literal["guided", "advanced"] | None = None
    has_onboarded: bool | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SSOStatus(BaseModel):
    """Whether single sign-on is available.

    Public, and safe to be: it says an option exists, which the button that
    uses it would say anyway. The issuer is included so the login page can
    name the provider rather than offering an anonymous "Sign in with SSO".
    """

    enabled: bool
    issuer: str | None
