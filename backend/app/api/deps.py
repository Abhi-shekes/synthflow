import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.api_key import ApiKeyScope
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
        if api_key.scope == ApiKeyScope.READ_ONLY and request.method not in READ_ONLY_METHODS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This API key is read-only and cannot {request.method}",
            )
        user = api_key.user
        if user is None:
            raise credentials_error
        api_keys.touch(db, api_key)
        # Recorded so `require_session` can refuse the key-management
        # routes. A leaked key that can mint more keys survives its own
        # revocation, which defeats the point of being able to revoke it.
        request.state.api_key = api_key
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
    return user


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
