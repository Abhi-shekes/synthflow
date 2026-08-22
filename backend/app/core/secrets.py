"""Encryption at rest for stored secrets.

Closes the gap `DatabaseConnection` documented from the day it was written:
an external database's password sat in the table in plaintext, so anyone
with a database dump or a read-only SQL account had every connected
system's credentials.

Design, and its limits stated plainly:

* The key is **derived from `SECRET_KEY`**, not stored separately. That
  keeps deployment to one secret instead of two, which is the difference
  between a feature people turn on and one they skip. It also means
  SECRET_KEY now protects data at rest as well as signing tokens —
  rotating it invalidates sessions *and* makes stored secrets
  undecryptable.
* This protects against **disclosure of the data at rest** — a dump, a
  backup, a stray SELECT. It does not protect against an attacker who has
  the application's environment, because such an attacker has SECRET_KEY
  and therefore the key. No key-derivation scheme fixes that; a KMS or an
  HSM is the answer, and this is deliberately not pretending to be one.
* Stored values carry a `enc:v1:` prefix so plaintext written before this
  existed is still readable. That makes the migration safe to run in
  either order and makes a half-migrated table work rather than crash.

Fernet is used rather than raw AES: it is authenticated (a tampered value
fails loudly instead of decrypting to garbage), versioned, and hard to
misuse. The salt is fixed rather than random because the derivation must
be deterministic — the same SECRET_KEY has to produce the same key on
every process and every restart, so there is nowhere to keep a per-value
salt. A fixed salt is acceptable here precisely because SECRET_KEY is
already required to be high-entropy; it is not acceptable for passwords,
which is why user passwords use bcrypt (app.core.security) and not this.
"""

from __future__ import annotations

import base64
import functools

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import String, TypeDecorator

from app.core.config import settings

# Marks a value as encrypted by this module, and which scheme produced it.
# Anything without this prefix is treated as legacy plaintext.
PREFIX = "enc:v1:"

# Fixed, and safe to be public — see the module docstring on why the
# derivation has to be deterministic.
_SALT = b"synthflow-secret-encryption-v1"
_ITERATIONS = 480_000


class SecretDecryptionError(RuntimeError):
    """A stored secret could not be decrypted with the current SECRET_KEY.

    Almost always means SECRET_KEY changed after the value was written.
    Raised rather than returning an empty string, because silently handing
    a connector a blank password produces a confusing auth failure a long
    way from the actual cause.
    """


@functools.lru_cache(maxsize=1)
def _fernet() -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Empty stays empty — an absent password
    is not a secret, and encrypting "" would make an empty password
    indistinguishable from a set one in the database."""
    if not plaintext:
        return plaintext
    token = _fernet().encrypt(plaintext.encode()).decode()
    return f"{PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret, passing legacy plaintext through unchanged."""
    if not stored or not stored.startswith(PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "A stored secret could not be decrypted. This usually means "
            "SECRET_KEY changed since it was saved; re-enter the credential "
            "to store it under the current key."
        ) from exc


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(PREFIX)


class EncryptedString(TypeDecorator):
    """A String column whose value is encrypted in the database and plain
    in Python.

    Using a column type rather than encrypting at the call sites means a
    future field that forgets to encrypt is impossible — there is no path
    that writes the column without going through here. The length is
    generous because a Fernet token is roughly 1.5x the plaintext plus
    ~100 bytes of overhead.
    """

    impl = String(1024)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt_secret(value)
