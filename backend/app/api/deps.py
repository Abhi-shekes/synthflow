import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.api_key import ApiKeyScope
from app.models.audit import ActorKind
from app.models.user import User
from app.services import api_keys

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# A read-only key may use these and nothing else. Enforced by method rather
# than by an endpoint list, because an endpoint list is a thing you forget to
# update when you add an endpoint — and forgetting, there, means a read-only
# key that can write.
READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The caller, whether they authenticated with a session or an API key.

    Both arrive as a bearer token, deliberately: every existing route,
    client and test keeps working untouched, and a CI pipeline sets the same
    header a browser does. An API key is recognised by its `sfk_` prefix, so
    the two never have to be told apart by guessing.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if api_keys.parse(token) is not None:
        api_key = api_keys.verify(db, token)
        if api_key is None:
            raise credentials_error
        user = api_key.user
        if user is None:
            raise credentials_error

        # Both of these are recorded *before* the scope check, not after it.
        # The credential is already proven at this point, so the caller is
        # known — and a request that is about to be refused is exactly the
        # one an audit log exists to show. Recording on the success path
        # only meant every 403 arrived with no "who" attached and the
        # middleware skipped it, so the log silently dropped the refusals.
        request.state.api_key = api_key
        _remember_actor(request, user, ActorKind.API_KEY, api_key.prefix)

        if api_key.scope == ApiKeyScope.READ_ONLY and request.method not in READ_ONLY_METHODS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This API key is read-only and cannot {request.method}",
            )
        api_keys.touch(db, api_key)
        return user

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    _remember_actor(request, user, ActorKind.SESSION, None)
    return user


def _remember_actor(
    request: Request, user: User, kind: ActorKind, api_key_prefix: str | None
) -> None:
    """Leave the caller's identity on the request for the audit middleware.

    The middleware runs outside dependency injection and has no way to
    authenticate on its own; doing it twice would mean two lookups per
    request and two chances to disagree. Email and key prefix are copied
    rather than referenced, because by the time the middleware reads them
    the session that loaded the user is closed.
    """
    request.state.actor = {
        "user_id": user.id,
        "actor_email": user.email,
        "actor_kind": kind,
        "api_key_prefix": api_key_prefix,
    }


def require_session(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """Like `get_current_user`, but refuses an API key.

    Guards the key-management routes only. A leaked full-scope key that can
    mint more keys outlives its own revocation — you revoke the one you know
    about and the one it created keeps working — so minting stays something
    only a logged-in person can do. GitHub draws the same line for the same
    reason.
    """
    if getattr(request.state, "api_key", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "API keys cannot manage API keys. Sign in to create or revoke one — "
                "a key that can mint keys would outlive its own revocation."
            ),
        )
    return current_user
