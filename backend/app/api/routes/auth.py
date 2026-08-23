from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessToken,
    RefreshRequest,
    SSOStatus,
    TokenPair,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from app.services import oidc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    subject = str(user.id)
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


@router.post("/refresh", response_model=AccessToken)
def refresh(payload: RefreshRequest) -> AccessToken:
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise ValueError("not a refresh token")
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc

    return AccessToken(access_token=create_access_token(decoded["sub"]))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Guided/advanced mode and onboarding completion — a user's own
    preferences, so no other route needs to touch this record."""
    if payload.ui_mode is not None:
        current_user.ui_mode = payload.ui_mode
    if payload.has_onboarded is not None:
        current_user.has_onboarded = payload.has_onboarded
    db.commit()
    db.refresh(current_user)
    return current_user


# --------------------------------------------------------------------------
# Single sign-on (OpenID Connect)
# --------------------------------------------------------------------------


@router.get("/sso", response_model=SSOStatus)
def sso_status() -> SSOStatus:
    """Whether SSO is configured, so the login page knows whether to offer
    it. Public: it reveals only that an option exists, which the button
    would reveal anyway."""
    return SSOStatus(enabled=oidc.enabled(), issuer=settings.OIDC_ISSUER or None)


@router.get("/sso/login")
def sso_login(request: Request, next: str | None = None) -> RedirectResponse:
    """Start a sign-in by sending the browser to the identity provider.

    The redirect URI is derived from this request rather than configured
    separately, so it is always exactly the callback that will run — a
    mismatch between the two is the single most common way an OIDC setup
    fails, and computing it removes the chance to get it wrong.
    """
    redirect_uri = str(request.url_for("sso_callback"))
    try:
        return RedirectResponse(oidc.authorization_url(redirect_uri, next))
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/sso/callback", name="sso_callback")
def sso_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Finish a sign-in and hand the browser its tokens.

    Tokens go back in the URL **fragment**, not the query string. A fragment
    is never sent to a server, so it stays out of access logs, proxy logs
    and `Referer` headers — the query string would put a working credential
    in all three.
    """
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The identity provider refused the sign-in: {error_description or error}",
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That callback is missing its code or state",
        )

    try:
        result = oidc.exchange(code, state)
        user = oidc.user_for(db, result["claims"])
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    subject = str(user.id)
    fragment = urlencode(
        {
            "access_token": create_access_token(subject),
            "refresh_token": create_refresh_token(subject),
        }
    )
    destination = result.get("next") or settings.OIDC_POST_LOGIN_URL
    return RedirectResponse(f"{destination}#{fragment}")
