import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limit_login, limit_refresh, limit_signup
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password_constant_time,
)
from app.db.session import get_db
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.schemas.auth import (
    AccessToken,
    SSOStatus,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from app.services import oidc, sessions

router = APIRouter(prefix="/auth", tags=["auth"])

# Not "/" — scoped to the auth routes only, so the browser never attaches
# this cookie to an unrelated API call. Smaller leak surface, and nothing
# outside this file ever needs to read it.
REFRESH_COOKIE_NAME = "synthflow_refresh"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60

# After this many wrong passwords in a row, further attempts are refused
# for a backoff that doubles each time — slow enough to make guessing
# impractical, short enough that a real user who mistyped a few times isn't
# locked out for long.
LOCKOUT_THRESHOLD = 5
LOCKOUT_BASE_SECONDS = 30
LOCKOUT_MAX_SECONDS = 60 * 60


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


def _issue_session(db: Session, user: User) -> tuple[str, str]:
    """Create a session row and its matching token pair. The caller is
    responsible for setting the refresh cookie on whatever Response it
    actually returns — a route that returns a RedirectResponse directly
    (sso_callback) bypasses the injected Response entirely, so the cookie
    has to be set on that object, not here."""
    session = sessions.create(db, user.id)
    db.commit()
    subject = str(user.id)
    access_token = create_access_token(subject)
    refresh_token = create_refresh_token(subject, str(session.id))
    return access_token, refresh_token


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(
    payload: UserCreate, db: Session = Depends(get_db), _: None = Depends(limit_signup)
) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=AccessToken)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(limit_login),
) -> AccessToken:
    user = db.query(User).filter(User.email == payload.email).first()
    now = datetime.now(UTC)

    if user is not None and user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again in a few minutes.",
            )

    # Runs even when `user` is None, against a dummy hash — a login for an
    # email that doesn't exist must cost exactly what a wrong password
    # costs, or the response time alone enumerates every registered email.
    password_ok = verify_password_constant_time(
        payload.password, user.hashed_password if user else None
    )

    if user is None or not password_ok:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
                backoff = min(
                    LOCKOUT_BASE_SECONDS * 2 ** (user.failed_login_attempts - LOCKOUT_THRESHOLD),
                    LOCKOUT_MAX_SECONDS,
                )
                user.locked_until = now + timedelta(seconds=backoff)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    access_token, refresh_token = _issue_session(db, user)
    _set_refresh_cookie(response, refresh_token)
    return AccessToken(access_token=access_token)


@router.post("/refresh", response_model=AccessToken)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(limit_refresh),
) -> AccessToken:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise invalid

    try:
        decoded = decode_token(token)
        if decoded.get("type") != "refresh":
            raise ValueError("not a refresh token")
        session_id = uuid.UUID(decoded["jti"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise invalid from exc

    session = sessions.get_live(db, session_id)
    if session is None:
        # Either genuinely unknown/expired, or a rotated-out token being
        # replayed — the signature of a stolen refresh token used after the
        # legitimate owner already refreshed. Either way the cookie this
        # request carried is dead; stop sending it back.
        _clear_refresh_cookie(response)
        raise invalid

    user = db.get(User, session.user_id)
    if user is None:
        _clear_refresh_cookie(response)
        raise invalid

    # Rotation: this refresh token is now spent. A new one replaces it, so
    # a leaked-and-later-replayed token is caught by the branch above
    # instead of silently working forever.
    sessions.revoke(db, session)
    db.commit()

    access_token, new_refresh_token = _issue_session(db, user)
    _set_refresh_cookie(response, new_refresh_token)
    return AccessToken(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Ends the session behind whatever refresh cookie this request
    carries. Never errors on a missing/invalid/already-dead cookie — the
    caller wanted to be logged out, and after this they are, regardless of
    which of those was true going in."""
    _clear_refresh_cookie(response)
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        return
    try:
        decoded = decode_token(token)
        session_id = uuid.UUID(decoded["jti"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return
    session = db.get(RefreshSession, session_id)
    if session is not None:
        sessions.revoke(db, session)
        db.commit()


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

    The access token goes back in the URL **fragment**, not the query
    string. A fragment is never sent to a server, so it stays out of access
    logs, proxy logs and `Referer` headers — the query string would put a
    working credential in all three. The refresh token doesn't travel this
    way at all: it goes straight into the httpOnly cookie set on this same
    redirect response, the same as a password login.

    A RedirectResponse is returned directly here rather than going through
    the injected Response dependency — FastAPI ignores that dependency's
    headers once a handler returns its own Response instance, so the
    cookie has to be set on this object specifically.
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

    access_token, refresh_token = _issue_session(db, user)
    fragment = urlencode({"access_token": access_token})
    destination = result.get("next") or settings.OIDC_POST_LOGIN_URL
    redirect = RedirectResponse(f"{destination}#{fragment}")
    _set_refresh_cookie(redirect, refresh_token)
    return redirect
