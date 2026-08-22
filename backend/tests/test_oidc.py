"""Phase 14 — single sign-on over OpenID Connect.

These tests stand alone: they mint an RSA key, sign id_tokens with it, and
serve a discovery document and JWKS from a stub. CI has no identity
provider, and a suite that needs one is a suite that does not run.

The flow *was* verified against a real IdP — Dex, behind the `sso` compose
profile — because a mock agrees with whatever you wrote. What the mock is
for is the cases a real IdP will not produce on demand: a signature from the
wrong key, a replayed nonce, an unverified email.
"""

import base64
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services import oidc

ISSUER = "https://idp.test/realm"
CLIENT_ID = "synthflow-test"
REDIRECT_URI = "http://testserver/api/v1/auth/sso/callback"


def _pem(key) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _b64(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture()
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def idp(monkeypatch, rsa_key):
    """A stub identity provider: discovery, JWKS and a token endpoint."""
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "shh")
    oidc.reset_cache()

    numbers = rsa_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key",
                "use": "sig",
                "alg": "RS256",
                "n": _b64(numbers.n),
                "e": _b64(numbers.e),
            }
        ]
    }
    document = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/auth",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/keys",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    state = {"id_token": None}

    def fake_urlopen(request, timeout=None, **kwargs):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/.well-known/openid-configuration"):
            return _Response(document)
        if url.endswith("/keys"):
            return _Response(jwks)
        if url.endswith("/token"):
            return _Response({"id_token": state["id_token"], "access_token": "opaque"})
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("app.services.oidc.urllib.request.urlopen", fake_urlopen)
    # PyJWKClient fetches the JWKS through its own urllib call.
    monkeypatch.setattr("jwt.jwks_client.urllib.request.urlopen", fake_urlopen)

    def sign(claims: dict, key=None) -> str:
        return jwt.encode(
            claims,
            _pem(key or rsa_key),
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    def issue(nonce: str, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "abc123",
            "email": "sso@example.com",
            "email_verified": True,
            "nonce": nonce,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(overrides)
        for key, value in list(overrides.items()):
            if value is None:
                claims.pop(key, None)
        state["id_token"] = sign(claims)
        return state["id_token"]

    yield type(
        "IdP",
        (),
        {"issue": staticmethod(issue), "sign": staticmethod(sign), "state": state},
    )
    oidc.reset_cache()


def _start() -> tuple[str, str]:
    """Begin a login and pull the state and nonce back out of the URL."""
    query = parse_qs(urlparse(oidc.authorization_url(REDIRECT_URI)).query)
    return query["state"][0], query["nonce"][0]


def _callback(client, state, code="abc"):
    return client.get(
        f"/api/v1/auth/sso/callback?code={code}&state={state}", follow_redirects=False
    )


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_sso_is_off_until_all_three_settings_are_present(monkeypatch):
    """The right default for a local install: the password login is the only
    way in until someone deliberately configures an issuer."""
    monkeypatch.setattr(settings, "OIDC_ISSUER", "")
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "")
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "")
    assert oidc.enabled() is False

    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    assert oidc.enabled() is False, "an issuer alone is not a configuration"


def test_the_status_endpoint_says_whether_sso_is_available(client, idp):
    response = client.get("/api/v1/auth/sso")
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "issuer": ISSUER}


def test_starting_a_login_without_configuration_says_so(client, monkeypatch):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "")
    response = client.get("/api/v1/auth/sso/login", follow_redirects=False)
    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]


# --------------------------------------------------------------------------
# The authorization request
# --------------------------------------------------------------------------


def test_the_authorization_url_carries_a_signed_state_and_a_nonce(idp):
    state, nonce = _start()
    payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["type"] == "oidc_state"
    assert payload["redirect_uri"] == REDIRECT_URI
    assert len(nonce) > 20


def test_a_login_redirects_the_browser_to_the_identity_provider(client, idp):
    response = client.get("/api/v1/auth/sso/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith(f"{ISSUER}/auth?")


# --------------------------------------------------------------------------
# The callback
# --------------------------------------------------------------------------


def test_a_valid_code_provisions_an_account_and_returns_tokens(client, idp):
    state, nonce = _start()
    idp.issue(nonce)

    response = _callback(client, state)
    assert response.status_code in (302, 307), response.text

    location = response.headers["location"]
    # Tokens ride in the fragment, never the query string: a fragment is not
    # sent to a server, so the credential stays out of access logs, proxy
    # logs and Referer headers.
    assert "#" in location
    assert "access_token=" not in location.split("#")[0]

    fragment = parse_qs(location.split("#", 1)[1])
    access = fragment["access_token"][0]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "sso@example.com"


def test_signing_in_twice_reuses_the_same_account(client, idp):
    for _ in range(2):
        state, nonce = _start()
        idp.issue(nonce)
        assert _callback(client, state).status_code in (302, 307)

    # Signing up locally with the same address must now collide, which is
    # how we know exactly one account exists.
    duplicate = client.post(
        "/api/v1/auth/signup",
        json={"email": "sso@example.com", "password": "testpassword123"},
    )
    assert duplicate.status_code == 409


def test_a_replayed_nonce_is_refused(client, idp):
    """The check that stops an id_token obtained elsewhere being replayed
    into this login. Nothing visibly breaks without it, which is exactly why
    it gets skipped."""
    state, _ = _start()
    idp.issue("a-nonce-from-somewhere-else")

    response = _callback(client, state)
    assert response.status_code == 400
    assert "different sign-in attempt" in response.json()["detail"]


def test_an_id_token_signed_by_the_wrong_key_is_refused(client, idp):
    state, nonce = _start()
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    idp.state["id_token"] = idp.sign(
        {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "abc123",
            "email": "sso@example.com",
            "email_verified": True,
            "nonce": nonce,
            "iat": now,
            "exp": now + 300,
        },
        key=attacker,
    )

    response = _callback(client, state)
    assert response.status_code == 400
    assert "did not verify" in response.json()["detail"]


def test_an_id_token_for_another_audience_is_refused(client, idp):
    state, nonce = _start()
    idp.issue(nonce, aud="some-other-app")
    assert _callback(client, state).status_code == 400


def test_an_expired_id_token_is_refused(client, idp):
    state, nonce = _start()
    past = int(time.time()) - 3600
    idp.issue(nonce, iat=past, exp=past + 60)
    assert _callback(client, state).status_code == 400


def test_a_forged_state_is_refused(client, idp):
    forged = jwt.encode(
        {
            "nonce": "x",
            "redirect_uri": REDIRECT_URI,
            "next": "",
            "type": "oidc_state",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "not-the-secret",
        algorithm="HS256",
    )
    response = _callback(client, forged)
    assert response.status_code == 400
    assert "expired or was tampered with" in response.json()["detail"]


def test_an_expired_state_is_refused(client, idp):
    stale = jwt.encode(
        {
            "nonce": "x",
            "redirect_uri": REDIRECT_URI,
            "next": "",
            "type": "oidc_state",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert _callback(client, stale).status_code == 400


def test_an_access_token_cannot_be_used_as_a_state(client, idp):
    """Every token this app signs uses the same key, so `type` is what stops
    one kind being presented as another."""
    from app.core.security import create_access_token

    response = _callback(client, create_access_token(str(uuid.uuid4())))
    assert response.status_code == 400
    assert "not a sign-in state token" in response.json()["detail"]


def test_an_unverified_email_is_refused(client, idp):
    """An IdP that lets anyone claim an unverified address is an IdP that
    lets anyone take over an existing account by signing up with its
    email."""
    state, nonce = _start()
    idp.issue(nonce, email_verified=False)

    response = _callback(client, state)
    assert response.status_code == 400
    assert "not verified" in response.json()["detail"]


def test_an_identity_with_no_email_is_refused(client, idp):
    state, nonce = _start()
    idp.issue(nonce, email=None, email_verified=None)

    response = _callback(client, state)
    assert response.status_code == 400
    assert "email" in response.json()["detail"]


def test_an_error_from_the_identity_provider_is_reported(client, idp):
    response = client.get(
        "/api/v1/auth/sso/callback?error=access_denied&error_description=User+said+no",
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "User said no" in response.json()["detail"]


def test_a_callback_missing_its_code_is_refused(client, idp):
    response = client.get("/api/v1/auth/sso/callback", follow_redirects=False)
    assert response.status_code == 400
    assert "missing its code or state" in response.json()["detail"]
