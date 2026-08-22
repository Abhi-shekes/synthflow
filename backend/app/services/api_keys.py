"""Long-lived credentials for machines.

A JWT lasts minutes and is obtained by typing a password. CI can do neither,
so before this there was no supported way to call SynthFlow from a pipeline
at all.

The whole design is in three decisions:

* **The secret is hashed with SHA-256, not bcrypt.** An API key is 32 random
  bytes; there is nothing to guess, so bcrypt's deliberate slowness buys no
  security and costs every request. See `ApiKey`'s docstring.
* **A prefix is stored in the clear** so verification is one indexed lookup
  rather than hashing against every row.
* **The key is returned exactly once.** Same rule as every other secret in
  this project.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey, ApiKeyScope

# `sfk` for SynthFlow key. A recognisable prefix is what lets a secret
# scanner spot one in a committed file, which is the failure mode that
# actually happens to API keys.
KEY_PREFIX = "sfk"
PREFIX_BYTES = 6
SECRET_BYTES = 32

# `last_used_at` is for answering "is anything still using this key", so
# second-level precision is not worth a database write on every request.
TOUCH_INTERVAL = timedelta(minutes=1)


class ApiKeyError(ValueError):
    pass


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate(
    db: Session,
    user_id: uuid.UUID,
    name: str,
    scope: ApiKeyScope = ApiKeyScope.FULL,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Mint a key. Returns the row and the secret, which is the only time
    the secret exists anywhere readable."""
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ApiKeyError("An expiry in the past would create a key that is already dead")

    prefix = secrets.token_hex(PREFIX_BYTES)
    secret = secrets.token_urlsafe(SECRET_BYTES)
    presented = f"{KEY_PREFIX}_{prefix}_{secret}"

    api_key = ApiKey(
        user_id=user_id,
        name=name,
        prefix=prefix,
        key_hash=_hash(presented),
        scope=scope,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.flush()
    return api_key, presented


def parse(presented: str) -> str | None:
    """The prefix out of a presented key, or None if it is not one.

    Returning None rather than raising is what lets `get_current_user` try
    the token as a JWT instead: the two credential kinds share one header,
    so "this is not an API key" is an ordinary outcome, not an error.
    """
    # maxsplit=2, not a bare split: `secrets.token_urlsafe` draws from an
    # alphabet that includes `_`, so roughly half of all secrets contain
    # one. Splitting on every underscore left those keys with four or more
    # parts, `parse` returned None, the auth dependency fell through to
    # trying them as a JWT, and they 401'd — intermittently, which is what
    # made it look like test-order flakiness rather than a bug.
    parts = presented.split("_", 2)
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        return None
    prefix = parts[1]
    if len(prefix) != PREFIX_BYTES * 2:
        return None
    return prefix


def verify(db: Session, presented: str) -> ApiKey | None:
    """The key behind a presented secret, if it is live.

    Returns None for every kind of failure — unknown, revoked, expired,
    wrong secret — rather than saying which. A caller that learns *why* a
    key was rejected learns whether a prefix exists, and the response is
    identical either way for the same reason a login does not say whether
    the email was the wrong half.
    """
    prefix = parse(presented)
    if prefix is None:
        return None

    api_key = db.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
    if api_key is None:
        return None

    # Constant time: a plain `==` on a hex digest leaks, through timing, how
    # many leading characters were right.
    if not hmac.compare_digest(api_key.key_hash, _hash(presented)):
        return None

    now = datetime.now(UTC)
    if api_key.revoked_at is not None:
        return None
    if api_key.expires_at is not None:
        expires = api_key.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= now:
            return None
    return api_key


def touch(db: Session, api_key: ApiKey) -> None:
    """Record use, at most once a `TOUCH_INTERVAL`.

    Writing on every request would turn a read-only API call into a write,
    which matters most for exactly the workload API keys exist to serve: a
    pipeline hammering an endpoint in a loop.
    """
    now = datetime.now(UTC)
    last = api_key.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last is None or now - last >= TOUCH_INTERVAL:
        api_key.last_used_at = now
        db.commit()


def revoke(db: Session, api_key: ApiKey) -> None:
    """Mark a key dead, keeping the row.

    Deleting it would lose the record that the key ever existed, which is
    exactly what someone investigating an incident needs. Revoking twice is
    a no-op rather than an error — the caller wanted it dead, and it is.
    """
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        db.commit()
