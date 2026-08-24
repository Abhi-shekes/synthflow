"""Create, look up, and revoke refresh sessions.

See `app.models.refresh_session.RefreshSession` for why this table exists.
Refresh is one-time-use (rotation): every `/auth/refresh` call revokes the
session it was presented with and creates a new one (`app.api.routes.auth`
does the rotation; this module only holds the row-level operations).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refresh_session import RefreshSession


def create(db: Session, user_id: uuid.UUID) -> RefreshSession:
    session = RefreshSession(
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    db.add(session)
    db.flush()
    return session


def get_live(db: Session, session_id: uuid.UUID) -> RefreshSession | None:
    """The session for a presented refresh token's `jti`, or None if it was
    never valid, has already been revoked (including by rotation — reusing
    a rotated-out refresh token, the signature of a stolen one being
    replayed, hits this path), or has expired."""
    session = db.get(RefreshSession, session_id)
    if session is None:
        return None
    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if session.revoked_at is not None or expires_at <= now:
        return None
    return session


def revoke(db: Session, session: RefreshSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
