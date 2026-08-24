from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


# A precomputed bcrypt hash of no real password, so a login for an email
# that doesn't exist still pays bcrypt's cost — see app.api.routes.auth.login.
# Otherwise a nonexistent-email request returns instantly while a
# wrong-password one takes a full bcrypt round trip, and that timing gap is
# enough to enumerate every registered email address at scale.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"not-a-real-account", bcrypt.gensalt()).decode("utf-8")


def verify_password_constant_time(password: str, hashed_password: str | None) -> bool:
    """Like `verify_password`, but always costs one bcrypt check even when
    there is no real hash to check against (`hashed_password is None`)."""
    return bcrypt.checkpw(
        password.encode("utf-8"), (hashed_password or _DUMMY_PASSWORD_HASH).encode("utf-8")
    )


def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh"],
    jti: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(subject, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(subject: str, jti: str) -> str:
    """`jti` is a `RefreshSession` id (see app.services.sessions) — it's
    what makes this token revocable despite being a stateless JWT: decoding
    proves the signature, but `/auth/refresh` and `/auth/logout` also
    require the session behind `jti` to still be live."""
    return _create_token(
        subject, timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES), "refresh", jti=jti
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
