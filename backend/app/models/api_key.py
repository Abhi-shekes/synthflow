import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ApiKeyScope(enum.StrEnum):
    """What a key is allowed to do.

    Two, not a permission matrix. The thing this exists for is calling
    SynthFlow from CI, and CI does one of two things: read a project to seed
    a test database, or drive generation. A read-only key is the one worth
    having because it is the one you can paste into a pipeline definition
    with less at stake; anything finer belongs with per-project permissions,
    which is a different bullet and a different model.

    READ_ONLY permits GET and HEAD. It is enforced by method rather than by
    an endpoint list, because an endpoint list is a thing you forget to
    update when you add an endpoint — and forgetting, there, means a
    read-only key that can write.
    """

    READ_ONLY = "read_only"
    FULL = "full"


class ApiKey(Base):
    """A long-lived credential for machines.

    Until now the only authentication was a user-password login producing a
    short-lived JWT, which means there was no supported way to call
    SynthFlow from CI at all: a pipeline cannot re-enter a password, and
    storing one so it can is worse than the problem.

    **The secret is stored as a SHA-256 hash, not bcrypt**, and that is a
    deliberate departure from how user passwords are stored two files over.
    bcrypt is slow on purpose, because a password is low-entropy and its
    hash must resist an offline guessing attack. An API key is 32 bytes from
    `secrets.token_urlsafe` — there is nothing to guess — so the slowness
    buys no security and costs every single request. Fast hashing is correct
    here for the same reason slow hashing is correct there.

    `prefix` is stored in the clear and indexed. Verification would
    otherwise mean hashing the presented key against every row in the table,
    which is O(keys) per request; with a prefix it is one indexed lookup and
    one constant-time compare. The prefix is also what a person sees in the
    UI to tell two keys apart, since the secret is never shown again.

    **Shown once, at creation.** Same rule as connection passwords and
    storage secrets: a credential that can be read back out of the API is a
    credential that leaks through logs, browser history and screenshots.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Public half. Unique and indexed so verification is one lookup.
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    # SHA-256 of the whole presented key, hex. See the class docstring for
    # why this is not bcrypt.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    scope: Mapped[ApiKeyScope] = mapped_column(
        Enum(ApiKeyScope), nullable=False, default=ApiKeyScope.FULL
    )

    # Null means it does not expire. Offered rather than required: a key
    # that expires is better practice, and a key that expires without anyone
    # having planned for it is an outage.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Revocation is a timestamp, not a row deletion. Deleting the row would
    # lose the record that the key ever existed, which is exactly what
    # someone investigating an incident needs.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Written at most once a minute — see `services.api_keys.touch`. The
    # question it answers is "is anything still using this key", and that
    # does not need second-level precision at the cost of a write per
    # request.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()
