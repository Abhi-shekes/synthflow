import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    # 12, not 8: this is the only thing standing between an internet-facing
    # signup form and a trivially guessable account, since brute force is
    # otherwise only slowed (not stopped) by rate limiting.
    password: str = Field(min_length=12)


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
