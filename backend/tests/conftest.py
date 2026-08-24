import ipaddress
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.rate_limit import login_limiter, refresh_limiter, signup_limiter
from app.db import session as db_session
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# The API process normally also runs the job worker (see app.main's
# lifespan, which reads this when TestClient enters its context below).
# Off here: tests drive the worker explicitly through jobs.tick(), and a
# loop running concurrently would race assertions about job status.
settings.RUN_WORKER = False

# Stands in for any hostname a test uses (see _offline_dns). Globally
# routable on purpose — the documentation ranges read as private to
# ipaddress, which the SSRF guard then refuses.
_PUBLIC_STUB_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _offline_dns():
    """Resolve hostnames without touching real DNS.

    The SSRF guard (app/core/network.py) resolves every hostname it is handed
    and refuses the ones that land on an internal address. That quietly made
    the suite depend on working DNS *and* on the test hostnames existing:
    `db.example.com` and `example.test` resolve nowhere, so on a CI runner
    every test that configures a database connection or a webhook died with
    "Could not resolve host" long before reaching the behaviour it was
    written to check.

    Names answer with a single globally-routable address, which the guard
    sees as an ordinary public host. It deliberately is *not* one of the
    RFC 5737 documentation ranges: Python's ipaddress module reports those
    as private, so the guard would refuse them and the stub would break the
    very tests it exists to unblock. Nothing ever connects to it — every
    test that gets this far has already mocked its transport.

    IP literals are passed through to the real resolver untouched, so the
    tests that assert the guard *does* refuse an internal address —
    test_ingest's 127.0.0.1 case — still resolve honestly and still fail
    closed.

    Patched by hand rather than through the `monkeypatch` fixture, and that
    is load-bearing: requesting `monkeypatch` from an autouse fixture makes
    pytest build it before every explicitly-requested fixture, which reverses
    its teardown position relative to `client`. test_metrics parks a bare
    `object()` in a producer registry and relies on monkeypatch unwinding
    that *before* the app's lifespan shutdown tries to `.cancel()` it.
    """
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        try:
            ipaddress.ip_address(str(host))
        except ValueError:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_STUB_IP, port or 0))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    socket.getaddrinfo = fake_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = real_getaddrinfo


@pytest.fixture()
def client():
    # The test client's "IP" (request.client.host) is the same synthetic
    # value on every request in every test, so the rate limiters below
    # would otherwise treat the whole suite as one caller and start
    # rejecting logins a handful of tests in.
    login_limiter.reset()
    signup_limiter.reset()
    refresh_limiter.reset()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Code reached outside FastAPI's DI (the websocket stream loop) looks up
    # `db_session.SessionLocal` fresh each call instead of importing it by
    # name, specifically so this swap reaches it too.
    original_session_local = db_session.SessionLocal
    db_session.SessionLocal = TestingSessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    db_session.SessionLocal = original_session_local
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def no_background_producers(monkeypatch):
    """Stop the output routes from launching real producer tasks.

    The hazard is the test database, not the code. conftest binds every
    session to ONE SQLite in-memory connection via `StaticPool`. A producer
    loads its batch on a worker thread through its own short-lived session,
    and that session's `close()` returns the shared connection to the pool
    — which rolls back whatever transaction is sitting on it. Land that
    between a DELETE's commit and the next read and the delete is silently
    undone: a 204, followed by the row still being listed. Production never
    hits it, because Postgres gives each session its own connection.

    Every route that starts a producer is patched, not just the one that
    happened to flake first. Four of the five had the same hazard and no
    protection; `test_create_list_and_delete_mqtt_output` was simply the
    one whose timing lost the race often enough to be noticed.

    Requested explicitly rather than autouse, because the tests that check
    a producer *actually delivers* need a real one — and a fixture that
    silently disabled the thing a test exists to check would be worse than
    the flake.
    """
    from app.api.routes import (
        kafka_outputs,
        mqtt_outputs,
        plugin_outputs,
        rabbitmq_outputs,
        webhook_outputs,
    )

    for module, name in (
        (mqtt_outputs, "start_mqtt_producer"),
        (kafka_outputs, "start_kafka_producer"),
        (rabbitmq_outputs, "start_rabbitmq_producer"),
        (webhook_outputs, "start_webhook_producer"),
        (plugin_outputs, "start_plugin_output"),
    ):
        monkeypatch.setattr(module, name, lambda output: None)


@pytest.fixture()
def auth_headers(client):
    password = "hunter222222"
    client.post("/api/v1/auth/signup", json={"email": "user@example.com", "password": password})
    resp = client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": password}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
