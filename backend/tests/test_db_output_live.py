"""Integration test against a real Postgres, for the one thing that can't be
verified with sqlite: actually writing rows into an external database.

Skipped unless TEST_EXTERNAL_PG_URL is set (postgresql://user:pass@host:port/db)
so normal `pytest` runs (and CI, until a Postgres service is wired up there)
don't depend on external infrastructure. Point it at any throwaway Postgres,
e.g.:

    docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=test postgres:16-alpine
    TEST_EXTERNAL_PG_URL=postgresql://postgres:test@localhost:5433/postgres \\
        pytest tests/test_db_output_live.py
"""

import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text

from app.models.database_connection import DatabaseConnection, DatabaseDialect
from app.models.field import EntityField, FieldType
from app.services.db_output import push_rows
from app.services.db_output import test_connection as check_connection

PG_URL = os.environ.get("TEST_EXTERNAL_PG_URL")

pytestmark = pytest.mark.skipif(not PG_URL, reason="set TEST_EXTERNAL_PG_URL to run")


def _connection_from_url(url: str) -> DatabaseConnection:
    parsed = urlparse(url)
    return DatabaseConnection(
        name="test",
        dialect=DatabaseDialect.POSTGRESQL,
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/"),
        username=parsed.username,
        password=parsed.password or "",
    )


def _field(name: str, field_type: FieldType) -> EntityField:
    f = EntityField(name=name, field_type=field_type)
    return f


def test_connection_reports_success():
    connection = _connection_from_url(PG_URL)
    ok, detail = check_connection(connection)
    assert ok, detail


def test_push_creates_table_and_inserts_rows():
    connection = _connection_from_url(PG_URL)
    fields = [
        _field("name", FieldType.STRING),
        _field("age", FieldType.INTEGER),
        _field("active", FieldType.BOOLEAN),
    ]
    rows = [
        {"name": "Ada", "age": 30, "active": True},
        {"name": "Grace", "age": 40, "active": False},
        {"name": None, "age": 25, "active": True},
    ]

    engine = create_engine(PG_URL.replace("postgresql://", "postgresql+psycopg://"))
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS synthflow_live_test"))

    written = push_rows(connection, fields, rows, "synthflow_live_test")
    assert written == 3

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT name, age, active FROM synthflow_live_test ORDER BY age")
        ).fetchall()
    assert result == [(None, 25, True), ("Ada", 30, True), ("Grace", 40, False)]

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE synthflow_live_test"))


def test_push_is_idempotent_on_table_creation():
    connection = _connection_from_url(PG_URL)
    fields = [_field("value", FieldType.INTEGER)]

    engine = create_engine(PG_URL.replace("postgresql://", "postgresql+psycopg://"))
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS synthflow_live_test_2"))

    push_rows(connection, fields, [{"value": 1}], "synthflow_live_test_2")
    written = push_rows(connection, fields, [{"value": 2}], "synthflow_live_test_2")
    assert written == 1

    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM synthflow_live_test_2")).scalar()
    assert count == 2

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE synthflow_live_test_2"))
