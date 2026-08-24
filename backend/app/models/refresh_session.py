"""Server-side record of every issued refresh token, so one can be killed.

A stateless JWT can't be revoked — anyone holding it stays valid until it
expires (up to REFRESH_TOKEN_EXPIRE_MINUTES, 7 days, from app.core.config).
Every refresh token this app issues carries this row's id as its `jti`
claim, so `/auth/logout` — and a stolen-token replay, see
`app.services.sessions` — can actually end a session instead of only
deleting the browser's copy of a credential that would otherwise keep
working from anywhere else for up to a week.

Revocation is a timestamp, not a row deletion, matching `ApiKey` two files
over: deleting the row would lose the record that the session ever
existed, which is exactly what someone investigating a token-theft
incident needs.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    # Also the refresh token's `jti` claim — one row per outstanding
    # refresh token, looked up by this id on every /auth/refresh call.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
