"""Phase 14 — API keys.

Before this there was no supported way to call SynthFlow from CI: the only
authentication was a password login producing a short-lived JWT, and a
pipeline cannot re-enter a password.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.db import session as db_session
from app.models.api_key import ApiKey
from app.services import api_keys


def _create(client, headers, **payload):
    body = {"name": "ci", **payload}
    response = client.post("/api/v1/api-keys", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _as_key(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


# --------------------------------------------------------------------------
# The point of the feature
# --------------------------------------------------------------------------


def test_a_key_authenticates_the_same_endpoints_a_session_does(client, auth_headers):
    """One header, two credential kinds — which is what lets every existing
    route, client and test keep working untouched."""
    created = _create(client, auth_headers)
    headers = _as_key(created["key"])

    project = client.post("/api/v1/projects", json={"name": "From CI"}, headers=headers)
    assert project.status_code == 201, project.text

    listed = client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert [p["name"] for p in listed.json()] == ["From CI"]


def test_the_secret_is_returned_once_and_never_again(client, auth_headers):
    created = _create(client, auth_headers)
    assert created["key"].startswith("sfk_")

    listed = client.get("/api/v1/api-keys", headers=auth_headers).json()
    assert len(listed) == 1
    assert "key" not in listed[0]
    # The prefix survives, so a person can still tell two keys apart.
    assert listed[0]["prefix"] in created["key"]


def test_a_key_sees_only_its_own_users_data(client, auth_headers):
    created = _create(client, auth_headers)
    client.post("/api/v1/projects", json={"name": "Mine"}, headers=auth_headers)

    client.post(
        "/api/v1/auth/signup",
        json={"email": "other@example.com", "password": "testpassword123"},
    )
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "testpassword123"},
    ).json()["access_token"]
    client.post(
        "/api/v1/projects",
        json={"name": "Theirs"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    visible = client.get("/api/v1/projects", headers=_as_key(created["key"])).json()
    assert [p["name"] for p in visible] == ["Mine"]


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_a_read_only_key_can_read_but_not_write(client, auth_headers):
    client.post("/api/v1/projects", json={"name": "Existing"}, headers=auth_headers)
    created = _create(client, auth_headers, scope="read_only")
    headers = _as_key(created["key"])

    assert client.get("/api/v1/projects", headers=headers).status_code == 200

    blocked = client.post("/api/v1/projects", json={"name": "Nope"}, headers=headers)
    assert blocked.status_code == 403
    assert "read-only" in blocked.json()["detail"]


def test_read_only_is_enforced_by_method_not_an_endpoint_list(client, auth_headers):
    """An endpoint list is a thing you forget to update when you add an
    endpoint, and forgetting there means a read-only key that can write."""
    project_id = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_headers).json()[
        "id"
    ]
    created = _create(client, auth_headers, scope="read_only")
    headers = _as_key(created["key"])

    for method, path in (
        ("post", f"/api/v1/projects/{project_id}/entities"),
        ("delete", f"/api/v1/projects/{project_id}"),
    ):
        response = getattr(client, method)(
            path, headers=headers, **({"json": {"name": "E"}} if method == "post" else {})
        )
        assert response.status_code == 403, f"{method} {path} was not blocked"


# --------------------------------------------------------------------------
# Revocation and expiry
# --------------------------------------------------------------------------


def test_a_revoked_key_stops_working_but_stays_visible(client, auth_headers):
    created = _create(client, auth_headers)
    headers = _as_key(created["key"])
    assert client.get("/api/v1/projects", headers=headers).status_code == 200

    revoked = client.delete(f"/api/v1/api-keys/{created['id']}", headers=auth_headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    assert client.get("/api/v1/projects", headers=headers).status_code == 401

    # Still listed. "This key was revoked last Tuesday" is the answer
    # someone investigating an incident needs.
    listed = client.get("/api/v1/api-keys", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["revoked_at"] is not None


def test_revoking_twice_keeps_the_original_timestamp(client, auth_headers):
    created = _create(client, auth_headers)
    first = client.delete(f"/api/v1/api-keys/{created['id']}", headers=auth_headers).json()
    second = client.delete(f"/api/v1/api-keys/{created['id']}", headers=auth_headers).json()
    # Moving it would rewrite when the revocation actually happened.
    assert first["revoked_at"] == second["revoked_at"]


def test_an_expired_key_is_refused(client, auth_headers):
    created = _create(
        client,
        auth_headers,
        expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    headers = _as_key(created["key"])
    assert client.get("/api/v1/projects", headers=headers).status_code == 200

    # Move the expiry into the past rather than sleeping. The session is
    # deliberately left open: conftest binds every session to one SQLite
    # connection, and closing a second one returns it to the pool, which
    # rolls back whatever transaction is on it — the same hazard
    # `no_background_producers` exists for.
    db = db_session.SessionLocal()
    key = db.get(ApiKey, uuid.UUID(created["id"]))
    key.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert client.get("/api/v1/projects", headers=headers).status_code == 401


def test_an_expiry_in_the_past_is_refused_at_creation(client, auth_headers):
    response = client.post(
        "/api/v1/api-keys",
        json={
            "name": "dead",
            "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already dead" in response.json()["detail"]


def test_a_key_cannot_manage_keys(client, auth_headers):
    """A leaked key that can mint keys outlives its own revocation: you
    revoke the one you know about and the one it created keeps working."""
    created = _create(client, auth_headers)
    headers = _as_key(created["key"])

    for call in (
        lambda: client.get("/api/v1/api-keys", headers=headers),
        lambda: client.post("/api/v1/api-keys", json={"name": "child"}, headers=headers),
        lambda: client.delete(f"/api/v1/api-keys/{created['id']}", headers=headers),
    ):
        response = call()
        assert response.status_code == 403, response.text
        assert "cannot manage API keys" in response.json()["detail"]


def test_another_users_key_cannot_be_revoked(client, auth_headers):
    created = _create(client, auth_headers)

    client.post(
        "/api/v1/auth/signup",
        json={"email": "intruder@example.com", "password": "testpassword123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "testpassword123"},
    ).json()["access_token"]

    response = client.delete(
        f"/api/v1/api-keys/{created['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# The credential itself
# --------------------------------------------------------------------------


def test_a_tampered_key_is_refused(client, auth_headers):
    created = _create(client, auth_headers)
    good = created["key"]
    # Same prefix, wrong secret — the case a lookup-by-prefix alone would
    # have waved through.
    tampered = good[:-1] + ("A" if good[-1] != "A" else "B")

    assert client.get("/api/v1/projects", headers=_as_key(tampered)).status_code == 401


def test_a_key_shaped_string_that_is_not_a_key_is_refused(client, auth_headers):
    assert (
        client.get("/api/v1/projects", headers=_as_key("sfk_deadbeefcafe_nonsense")).status_code
        == 401
    )


def test_a_jwt_still_works_alongside_keys(client, auth_headers):
    """Both credential kinds share one header, so the JWT path must be
    unaffected by the key path existing."""
    _create(client, auth_headers)
    assert client.get("/api/v1/projects", headers=auth_headers).status_code == 200


def test_a_secret_containing_an_underscore_still_parses():
    """`secrets.token_urlsafe` draws from an alphabet including `_`, so
    roughly half of all keys contain one. Splitting on every underscore made
    those keys unparseable, so they fell through to the JWT path and 401'd —
    intermittently, which read as test-order flakiness rather than a bug."""
    assert api_keys.parse("sfk_abcdef012345_has_underscores_in_it") == "abcdef012345"


def test_every_generated_key_parses_back_to_its_own_prefix(client, auth_headers):
    """A property, not an example: whatever the random secret contains, the
    key it is part of has to survive a round trip."""
    for i in range(25):
        created = _create(client, auth_headers, name=f"k{i}")
        assert api_keys.parse(created["key"]) == created["prefix"]
        assert client.get("/api/v1/projects", headers=_as_key(created["key"])).status_code == 200


def test_parse_rejects_anything_that_is_not_a_key():
    """`parse` returning None rather than raising is what lets the auth
    dependency fall through to trying the token as a JWT."""
    assert api_keys.parse("not-a-key") is None
    assert api_keys.parse("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def") is None
    assert api_keys.parse("sfk_short_secret") is None
    assert api_keys.parse("sfk_abcdef012345_secret") == "abcdef012345"


def test_two_keys_never_collide(client, auth_headers):
    keys = {_create(client, auth_headers, name=f"k{i}")["key"] for i in range(10)}
    assert len(keys) == 10
    prefixes = {k.split("_")[1] for k in keys}
    assert len(prefixes) == 10


def test_last_used_is_recorded(client, auth_headers):
    created = _create(client, auth_headers)
    listed = client.get("/api/v1/api-keys", headers=auth_headers).json()
    assert listed[0]["last_used_at"] is None

    client.get("/api/v1/projects", headers=_as_key(created["key"]))

    listed = client.get("/api/v1/api-keys", headers=auth_headers).json()
    assert listed[0]["last_used_at"] is not None


def test_the_key_list_is_paged_without_skipping_or_repeating(client, auth_headers):
    """Revoked keys stay forever by design, so "all of them" stops being a
    sensible response for an account that has rotated keys for a year.

    Paging is only correct if the order is total. `created_at` alone is not:
    keys minted in one burst share the database clock to the microsecond, so
    the tie fell to whatever the engine felt like and pages both repeated and
    skipped rows.
    """
    made = [_create(client, auth_headers, name=f"k{i}")["id"] for i in range(12)]

    seen: list[str] = []
    for offset in (0, 5, 10):
        page = client.get(f"/api/v1/api-keys?limit=5&offset={offset}", headers=auth_headers).json()
        seen.extend(k["id"] for k in page)

    assert len(seen) == 12
    assert set(seen) == set(made)

    # And the order is stable: the same query twice gives the same answer,
    # which is what a caller paging through it is relying on.
    again = client.get("/api/v1/api-keys?limit=12", headers=auth_headers).json()
    assert [k["id"] for k in again] == seen
