"""Writes generated rows into a user-configured external database.

PostgreSQL, MySQL and MongoDB (Phase 12). Postgres needs no extra — its
driver is already vendored for the app's own control-plane database —
while MySQL and MongoDB ship as optional extras, so a deployment that
pushes to neither carries neither driver. See app.services.install.

The two SQL dialects share everything: one URL table, one engine builder,
one insert path. MongoDB shares the connection model, the encrypted
password and the ownership checks, and diverges only where it must — no
CREATE TABLE, documents instead of rows, and structure preserved rather
than serialised to JSON strings. That is one dispatch in `push_rows`
rather than a parallel model and a parallel API.

Table/column definitions are built with SQLAlchemy Core (Table/Column), and
inserts go through `table.insert()` with parameterized values — never raw
string-formatted SQL — so the identifier quoting and value escaping are the
dialect's, not ours. The one thing we still validate ourselves is that table
and column names look like plain identifiers, so a bad name fails fast with a
clear message instead of a confusing driver-level error.
"""

import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.models.database_connection import DatabaseConnection, DatabaseDialect
from app.models.field import EntityField, FieldType, IdentifierPreset
from app.services import install

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")

_TYPE_MAP = {
    FieldType.STRING: lambda: String(255),
    FieldType.INTEGER: lambda: Integer(),
    FieldType.FLOAT: lambda: Float(),
    FieldType.BOOLEAN: lambda: Boolean(),
    FieldType.DATE: lambda: Date(),
    FieldType.DATETIME: lambda: DateTime(),
    FieldType.UUID: lambda: String(36),
    FieldType.ENUM: lambda: String(255),
    FieldType.ARRAY: lambda: Text(),
    FieldType.OBJECT: lambda: Text(),
    FieldType.JSON: lambda: Text(),
}


class DatabaseOutputError(ValueError):
    pass


def validate_identifier(name: str, kind: str) -> None:
    if not _IDENTIFIER_RE.match(name):
        raise DatabaseOutputError(
            f"{kind} '{name}' is not a safe SQL identifier — use only letters, digits, and "
            "underscores, and don't start with a digit (max 63 characters)"
        )


# Credentials go through quote_plus, not into the URL raw: a password
# containing '@', ':' or '/' would otherwise silently reshape the URL and
# produce a baffling "unknown host" instead of an auth error.
def _credentials(connection: DatabaseConnection) -> str:
    return f"{quote_plus(connection.username)}:{quote_plus(connection.password)}"


# Per-dialect connect timeout. The two drivers spell it differently, which
# is exactly the sort of thing that belongs in one table rather than in an
# if-branch at the call site.
_SQL_URLS = {
    DatabaseDialect.POSTGRESQL: ("postgresql+psycopg", {"connect_timeout": 5}),
    DatabaseDialect.MYSQL: ("mysql+pymysql", {"connect_timeout": 5}),
}


def build_engine(connection: DatabaseConnection) -> Engine:
    """A SQLAlchemy engine for a SQL dialect. MongoDB has no engine — see
    `_mongo_client` — so asking for one is a programming error rather than
    a user-facing condition."""
    entry = _SQL_URLS.get(connection.dialect)
    if entry is None:
        raise DatabaseOutputError(
            f"'{connection.dialect}' is not a SQL dialect and has no SQLAlchemy engine"
        )
    if connection.dialect == DatabaseDialect.MYSQL:
        install.require("mysql")

    driver, connect_args = entry
    url = (
        f"{driver}://{_credentials(connection)}"
        f"@{connection.host}:{connection.port}/{connection.database}"
    )
    return create_engine(url, connect_args=connect_args)


# Where MongoDB looks up the user, as opposed to where the data lives.
# Unlike SQL, these are routinely different: the official Docker image, and
# Atlas, both create users in `admin` and expect clients to say so. Without
# this, pymongo authenticates against the data database and a correct
# username/password fails with a bare "Authentication failed", which is a
# genuinely confusing thing to debug.
#
# Documented limitation: a deployment whose user was created *inside* the
# target database needs authSource to be that database instead. Making it
# configurable is a per-connection column and therefore a schema change.
MONGO_AUTH_SOURCE = "admin"


def _mongo_client(connection: DatabaseConnection):
    """A pymongo client. Imported inside the function, not at module scope,
    for the same reason the Kafka producer is — pymongo is an optional
    extra and the core install must import this module without it."""
    install.require("mongo")
    from pymongo import MongoClient

    url = (
        f"mongodb://{_credentials(connection)}"
        f"@{connection.host}:{connection.port}/{connection.database}"
        f"?authSource={MONGO_AUTH_SOURCE}"
    )
    return MongoClient(url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)


def test_connection(connection: DatabaseConnection) -> tuple[bool, str]:
    try:
        if connection.dialect == DatabaseDialect.MONGODB:
            client = _mongo_client(connection)
            try:
                # `ping` forces the driver to actually reach the server;
                # constructing a MongoClient is lazy and would "succeed"
                # against a host that isn't there.
                client.admin.command("ping")
            finally:
                client.close()
            return True, "Connected successfully"

        engine = build_engine(connection)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True, "Connected successfully"
    except DatabaseOutputError as exc:
        return False, str(exc)
    except SQLAlchemyError as exc:
        return False, str(exc.__cause__ or exc)
    except Exception as exc:  # pymongo raises its own hierarchy
        return False, str(exc)


def _coerce_value(value: Any, field_type: FieldType) -> Any:
    if value is None:
        return None
    if field_type == FieldType.DATE and isinstance(value, str):
        return datetime.fromisoformat(value).date()
    if field_type == FieldType.DATETIME and isinstance(value, str):
        return datetime.fromisoformat(value)
    if field_type in (FieldType.ARRAY, FieldType.OBJECT, FieldType.JSON):
        return json.dumps(value) if isinstance(value, (list, dict)) else value
    return value


def push_rows(
    connection: DatabaseConnection,
    fields: list[EntityField],
    rows: list[dict[str, Any]],
    table_name: str,
) -> int:
    """Creates `table_name` if it doesn't exist (columns inferred from
    `fields`) and inserts `rows` into it. Only the declared fields are
    written — any extra generation-time keys (e.g. a workflow field's
    `<field>_history`) are dropped, the same as CSV export, since a SQL
    table needs a fixed column set.

    For MongoDB `table_name` is the collection name, and the same
    declared-fields-only rule applies — see `_push_mongo` for why that is a
    deliberate choice there rather than an inherited limitation.
    """
    validate_identifier(table_name, "table_name")
    for field in fields:
        validate_identifier(field.name, "field name")

    if connection.dialect == DatabaseDialect.MONGODB:
        return _push_mongo(connection, fields, rows, table_name)

    engine = build_engine(connection)
    metadata = MetaData()
    # A qr_code preset's base64 PNG data URI is far longer than the
    # String(255) a plain STRING field otherwise gets — give it Text()
    # instead so a push doesn't silently truncate the image data.
    columns = [
        Column(
            f.name,
            Text() if f.preset == IdentifierPreset.QR_CODE else _TYPE_MAP[f.field_type](),
        )
        for f in fields
    ]
    table = Table(table_name, metadata, *columns)

    payload = [
        {f.name: _coerce_value(row.get(f.name), f.field_type) for f in fields} for row in rows
    ]

    try:
        with engine.begin() as conn:
            table.create(conn, checkfirst=True)
            if payload:
                conn.execute(table.insert(), payload)
    except SQLAlchemyError as exc:
        raise DatabaseOutputError(str(exc.__cause__ or exc)) from exc

    return len(payload)


def _mongo_value(value: Any, field_type: FieldType) -> Any:
    """Unlike the SQL path, structure is *kept*. `_coerce_value` serialises
    a list or dict to a JSON string because a SQL column can't hold one;
    MongoDB stores them natively, and flattening them to strings there
    would throw away the one thing a document store is for."""
    if value is None:
        return None
    if field_type == FieldType.DATE and isinstance(value, str):
        return datetime.fromisoformat(value).date().isoformat()
    if field_type == FieldType.DATETIME and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _push_mongo(
    connection: DatabaseConnection,
    fields: list[EntityField],
    rows: list[dict[str, Any]],
    collection_name: str,
) -> int:
    """Insert rows as documents.

    Restricted to the declared fields on purpose, matching the SQL path.
    MongoDB would happily accept the extra generation-time keys, but a
    collection whose document shape depends on which features an entity
    happens to use is worse than a predictable one — and a user who wants
    `<field>_history` can declare it. Being schemaless is not a reason to
    be shapeless.

    A DATE is stored as an ISO string rather than a datetime at midnight,
    because BSON has no date-only type and silently turning "2024-03-05"
    into a timestamp invents a time zone question nobody asked.
    """
    client = _mongo_client(connection)
    documents = [
        {f.name: _mongo_value(row.get(f.name), f.field_type) for f in fields} for row in rows
    ]
    try:
        if documents:
            client[connection.database][collection_name].insert_many(documents)
    except Exception as exc:
        raise DatabaseOutputError(str(exc)) from exc
    finally:
        client.close()

    return len(documents)
