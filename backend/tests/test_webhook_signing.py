"""Phase 12 — signed webhook output.

The signing scheme gets the most attention here because it is the part
whose failure is silent: a webhook that delivers is obviously working, but
a signature that verifies when it shouldn't looks identical to one that
works.
"""

import json
import time

import pytest

from app.services import webhook_signing

SECRET = "shared-secret"
BODY = json.dumps([{"id": 1, "name": "row"}]).encode()


def test_a_signature_verifies_against_the_same_body():
    signature, stamp = webhook_signing.sign(SECRET, BODY)
    assert webhook_signing.verify(SECRET, BODY, signature, stamp)


def test_a_signature_is_prefixed_with_its_algorithm():
    """So a future scheme can be added without receivers guessing which
    one they are looking at."""
    signature, _ = webhook_signing.sign(SECRET, BODY)
    assert signature.startswith("sha256=")


def test_a_changed_body_fails():
    signature, stamp = webhook_signing.sign(SECRET, BODY)
    assert not webhook_signing.verify(SECRET, BODY + b" ", signature, stamp)


def test_a_different_secret_fails():
    signature, stamp = webhook_signing.sign(SECRET, BODY)
    assert not webhook_signing.verify("other-secret", BODY, signature, stamp)


def test_a_replayed_request_with_a_fresh_timestamp_fails():
    """The whole reason the timestamp is *inside* the signed string. If it
    were only a header, an attacker could re-send a captured body with a
    current timestamp and the signature would still verify."""
    signature, _ = webhook_signing.sign(SECRET, BODY, timestamp=int(time.time()))
    assert not webhook_signing.verify(SECRET, BODY, signature, int(time.time()) + 1)


def test_an_old_request_is_rejected_even_though_its_signature_is_valid():
    old = int(time.time()) - 3600
    signature, _ = webhook_signing.sign(SECRET, BODY, timestamp=old)
    # The signature itself is genuine...
    assert webhook_signing.verify(SECRET, BODY, signature, old, max_age_seconds=0)
    # ...but it is outside the replay window.
    assert not webhook_signing.verify(SECRET, BODY, signature, old, max_age_seconds=300)


def test_a_missing_or_malformed_timestamp_fails_rather_than_raising():
    """A receiver gets these from the network, so garbage must be a
    `False`, not a traceback."""
    signature, _ = webhook_signing.sign(SECRET, BODY)
    assert not webhook_signing.verify(SECRET, BODY, signature, "not-a-number")
    assert not webhook_signing.verify(SECRET, BODY, signature, None)


def test_a_missing_signature_fails_rather_than_raising():
    assert not webhook_signing.verify(SECRET, BODY, "", int(time.time()))
    assert not webhook_signing.verify(SECRET, BODY, None, int(time.time()))


def test_the_same_body_at_the_same_second_signs_identically():
    """Determinism is what lets a receiver recompute the MAC at all."""
    first, stamp = webhook_signing.sign(SECRET, BODY, timestamp=1_700_000_000)
    second, _ = webhook_signing.sign(SECRET, BODY, timestamp=1_700_000_000)
    assert first == second


def test_signing_covers_the_exact_bytes_not_a_re_encoded_copy():
    """JSON is not canonical — key order and whitespace differ between
    encoders — so a receiver that re-serialises before verifying gets
    mysterious failures. Signing bytes is what avoids that."""
    compact = b'{"a":1,"b":2}'
    spaced = b'{"a": 1, "b": 2}'
    signature, stamp = webhook_signing.sign(SECRET, compact)
    assert webhook_signing.verify(SECRET, compact, signature, stamp)
    assert not webhook_signing.verify(SECRET, spaced, signature, stamp)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def _entity(client, headers):
    project_id = client.post("/api/v1/projects", json={"name": "Webhooks"}, headers=headers).json()[
        "id"
    ]
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Row"}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    )
    return project_id, entity["id"]


@pytest.fixture
def webhook_base(client, auth_headers):
    project_id, entity_id = _entity(client, auth_headers)
    return f"/api/v1/projects/{project_id}/entities/{entity_id}/webhook-outputs"


def test_creating_a_webhook_never_returns_its_secret(client, auth_headers, webhook_base):
    created = client.post(
        webhook_base,
        json={"url": "http://example.test/hook", "secret": "s3cr3t", "events_per_second": 1},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    assert "secret" not in created.json()
    assert created.json()["url"] == "http://example.test/hook"
    client.delete(f"{webhook_base}/{created.json()['id']}", headers=auth_headers)


def test_the_webhook_secret_is_encrypted_at_rest(client, auth_headers, webhook_base):
    from sqlalchemy import text

    from app.core.secrets import is_encrypted
    from app.db import session as db_session

    created = client.post(
        webhook_base,
        json={"url": "http://example.test/hook", "secret": "s3cr3t"},
        headers=auth_headers,
    ).json()
    db = db_session.SessionLocal()
    try:
        stored = db.execute(text("SELECT secret FROM webhook_outputs")).scalar()
    finally:
        db.close()
    assert is_encrypted(stored)
    assert "s3cr3t" not in stored
    client.delete(f"{webhook_base}/{created['id']}", headers=auth_headers)


def test_a_webhook_needs_no_optional_extra(client, auth_headers, webhook_base):
    """urllib and hmac are stdlib, so this works in the smallest install —
    unlike every other streaming output."""
    created = client.post(
        webhook_base, json={"url": "http://example.test/hook", "secret": "x"}, headers=auth_headers
    )
    assert created.status_code == 201
    client.delete(f"{webhook_base}/{created.json()['id']}", headers=auth_headers)


def test_a_webhook_appears_in_the_outputs_aggregate(client, auth_headers):
    project_id, entity_id = _entity(client, auth_headers)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/webhook-outputs"
    created = client.post(
        base, json={"url": "http://example.test/hook", "secret": "x"}, headers=auth_headers
    ).json()
    outputs = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers).json()
    assert any(o["type"] == "webhook" for o in outputs)
    client.delete(f"{base}/{created['id']}", headers=auth_headers)
