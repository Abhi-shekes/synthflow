"""Single sign-on over OpenID Connect.

Until now the only way to get an account was a password this application
stored. For a team that already has an identity provider, that is a second
place to offboard someone from — and the one everybody forgets.

**OIDC only. SAML is deliberately not implemented** — see ROADMAP.md. It
needs `xmlsec`, a native library with a real build burden on every platform
this ships to, and an IdP to verify against that cannot be stood up here.
This project's rule is that a connector nobody has run against its actual
service does not get ticked off, and an untested SAML implementation
handling XML signatures is a worse thing to ship than an honest gap.

Three decisions worth stating:

* **stdlib `urllib`, no new dependency.** `PyJWKClient` comes from PyJWT,
  which is already core because it signs the app's own sessions. That means
  single sign-on works in the smallest possible install — the same property
  the signed-webhook output has, and for the same reason.
* **Discovery is fetched, not configured.** An issuer publishes its
  endpoints at a well-known URL; copying them into settings by hand means
  three more things to get wrong and one more thing to update when the IdP
  moves them.
* **State is a signed token, not a database row.** It has to survive one
  redirect and prove nobody forged it, which a short-lived signed value does
  without a table, a cleanup job, or a shared store between replicas.
* **The `nonce` is checked.** It is the part of OIDC that stops an id_token
  obtained elsewhere being replayed into this login, and it is also the part
  most often skipped because nothing visibly breaks without it.
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User

# A login has to survive one redirect to the IdP and back. Long enough for
# someone to type a password and answer an MFA prompt, short enough that a
# state token found in a log is worthless.
STATE_TTL = timedelta(minutes=10)

_DISCOVERY_CACHE: dict[str, dict[str, Any]] = {}
_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


class OIDCError(ValueError):
    pass


def enabled() -> bool:
    return bool(settings.OIDC_ISSUER and settings.OIDC_CLIENT_ID and settings.OIDC_CLIENT_SECRET)


def _require_enabled() -> None:
    if not enabled():
        raise OIDCError(
            "Single sign-on is not configured. Set OIDC_ISSUER, OIDC_CLIENT_ID and "
            "OIDC_CLIENT_SECRET."
        )


def discovery(force: bool = False) -> dict[str, Any]:
    """The issuer's published endpoints.

    Cached per issuer for the process's lifetime. An IdP that moves its
    endpoints does so about as often as it changes its domain, and fetching
    a document on every login turns the IdP into a hard dependency of every
    request rather than of the ones that talk to it.
    """
    _require_enabled()
    issuer = settings.OIDC_ISSUER.rstrip("/")
    if force or issuer not in _DISCOVERY_CACHE:
        url = f"{issuer}/.well-known/openid-configuration"
        try:
            with urllib.request.urlopen(url, timeout=settings.OIDC_TIMEOUT_SECONDS) as response:
                document = json.loads(response.read())
        except Exception as exc:
            raise OIDCError(f"Could not read OIDC discovery from {url}: {exc}") from exc
        for required in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if required not in document:
                raise OIDCError(f"That issuer's discovery document has no {required}")
        _DISCOVERY_CACHE[issuer] = document
    return _DISCOVERY_CACHE[issuer]


def _jwks_client() -> PyJWKClient:
    uri = discovery()["jwks_uri"]
    if uri not in _JWKS_CLIENTS:
        # Caches keys and refetches on an unknown `kid`, which is what makes
        # an IdP's key rotation a non-event rather than an outage.
        _JWKS_CLIENTS[uri] = PyJWKClient(uri, cache_keys=True)
    return _JWKS_CLIENTS[uri]


def _sign_state(payload: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {**payload, "iat": now, "exp": now + STATE_TTL, "type": "oidc_state"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _read_state(state: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as exc:
        raise OIDCError("That sign-in attempt has expired or was tampered with") from exc
    if payload.get("type") != "oidc_state":
        raise OIDCError("That is not a sign-in state token")
    return payload


def authorization_url(redirect_uri: str, next_url: str | None = None) -> str:
    """Where to send the browser to start a login.

    `state` and `nonce` are both minted here and both travel in the signed
    state, so the callback can check the round trip without storing
    anything. `next_url` rides along so a login that started from a deep
    link comes back to it.
    """
    _require_enabled()
    document = discovery()

    nonce = secrets.token_urlsafe(24)
    state = _sign_state({"nonce": nonce, "redirect_uri": redirect_uri, "next": next_url or ""})

    query = urllib.parse.urlencode(
        {
            "client_id": settings.OIDC_CLIENT_ID,
            "response_type": "code",
            "scope": settings.OIDC_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
        }
    )
    return f"{document['authorization_endpoint']}?{query}"


def exchange(code: str, state: str) -> dict[str, Any]:
    """Turn an authorization code into verified id_token claims."""
    _require_enabled()
    payload = _read_state(state)
    document = discovery()

    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": payload["redirect_uri"],
            "client_id": settings.OIDC_CLIENT_ID,
            "client_secret": settings.OIDC_CLIENT_SECRET,
        }
    ).encode()
    request = urllib.request.Request(
        document["token_endpoint"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.OIDC_TIMEOUT_SECONDS) as response:
            tokens = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # The IdP's own message is far more useful than "login failed" — a
        # redirect_uri mismatch is the single most common setup error and it
        # says so explicitly.
        detail = exc.read().decode(errors="replace")[:300]
        raise OIDCError(f"The identity provider refused the code: {detail}") from exc
    except Exception as exc:
        raise OIDCError(f"Could not reach the identity provider: {exc}") from exc
    id_token = tokens.get("id_token")
    if not id_token:
        raise OIDCError("The identity provider returned no id_token")

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=document.get("id_token_signing_alg_values_supported", ["RS256"]),
            audience=settings.OIDC_CLIENT_ID,
            issuer=settings.OIDC_ISSUER.rstrip("/"),
        )
    except Exception as exc:
        raise OIDCError(f"That id_token did not verify: {exc}") from exc

    # The check that stops an id_token obtained somewhere else being
    # replayed into this login. Skipping it breaks nothing visibly, which is
    # exactly why it gets skipped.
    if claims.get("nonce") != payload["nonce"]:
        raise OIDCError("That id_token was issued for a different sign-in attempt")

    return {"claims": claims, "next": payload.get("next") or ""}


def user_for(db: Session, claims: dict[str, Any]) -> User:
    """Find or create the local account for a verified identity.

    **Email is the join key**, and `email_verified` is required when the
    issuer reports it. Without that check, an IdP that lets anyone claim an
    unverified address is an IdP that lets anyone take over an existing
    account by signing up with its email.

    A provisioned account gets a random password it will never be told.
    Leaving the column empty would mean a nullable password on every user
    row to serve a case nobody logs in with; a random one is unusable by
    construction and keeps the ordinary login path exactly as it was.
    """
    email = claims.get("email")
    if not email:
        raise OIDCError(
            "That identity provider returned no email address — SynthFlow identifies "
            "accounts by email, so the 'email' scope has to be granted"
        )
    if claims.get("email_verified") is False:
        raise OIDCError(f"{email} is not verified with the identity provider")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, hashed_password=hash_password(secrets.token_urlsafe(32)))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def reset_cache() -> None:
    """Forget discovery and keys. For tests, and for an IdP that moved."""
    _DISCOVERY_CACHE.clear()
    _JWKS_CLIENTS.clear()
