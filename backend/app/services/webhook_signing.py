"""Sign outgoing webhook payloads so a receiver can verify them.

The scheme, and what it does and does not prove.

A receiver gets three headers:

    X-SynthFlow-Timestamp: 1724328000
    X-SynthFlow-Signature: sha256=<hex>
    X-SynthFlow-Delivery:  <uuid>

The signature is `HMAC-SHA256(secret, "<timestamp>.<raw body>")`. Two
details matter:

* **The timestamp is inside the signed string**, not merely sent alongside
  it. If it were only a header, an attacker could replay a captured
  request with a fresh timestamp and the signature would still verify —
  which is exactly the attack the timestamp is meant to stop. A receiver
  rejects anything older than its tolerance (`MAX_AGE_SECONDS` is the
  suggestion) and the signature guarantees the timestamp was not edited.
* **The signature covers the raw body bytes**, not a re-serialised copy.
  JSON is not canonical — key order and whitespace differ between
  encoders — so verifying against a re-encoded body produces mysterious
  failures. `sign` takes bytes for that reason.

What it proves: the request was produced by someone holding the shared
secret, and the body has not been altered. What it does not prove: that
the request came from any particular host, or that the receiver is the
only one holding the secret. It is a shared-secret MAC, not a signature in
the public-key sense — anyone with the secret can produce a valid request,
including the receiver.

`verify` exists here rather than only in a receiver's codebase so the
project's own tests exercise the real thing, and so the docstring above has
a working reference implementation next to it.
"""

from __future__ import annotations

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-SynthFlow-Signature"
TIMESTAMP_HEADER = "X-SynthFlow-Timestamp"
DELIVERY_HEADER = "X-SynthFlow-Delivery"

# Suggested replay window for a receiver. Not enforced here — this side
# only signs — but stated so a receiver has a number to start from.
MAX_AGE_SECONDS = 300

_PREFIX = "sha256="


def signed_payload(timestamp: int, body: bytes) -> bytes:
    """The exact bytes that get MACed. Separated so `sign` and `verify`
    cannot drift apart, which is the classic way these schemes break."""
    return f"{timestamp}.".encode() + body


def sign(secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, int]:
    """Return `(signature_header_value, timestamp)`."""
    stamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), signed_payload(stamp, body), hashlib.sha256).hexdigest()
    return f"{_PREFIX}{digest}", stamp


def verify(
    secret: str,
    body: bytes,
    signature: str,
    timestamp: int | str,
    max_age_seconds: int = MAX_AGE_SECONDS,
) -> bool:
    """Reference implementation of the receiver's side.

    Uses `compare_digest`, not `==`: comparing MACs with a normal string
    comparison leaks how many leading bytes matched through timing, which
    is enough to forge one byte at a time.
    """
    try:
        stamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    if max_age_seconds > 0 and abs(int(time.time()) - stamp) > max_age_seconds:
        return False

    expected, _ = sign(secret, body, stamp)
    return hmac.compare_digest(expected, signature or "")
