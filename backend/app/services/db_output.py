"""Writes generated rows into a user-configured external database.

Scoped to PostgreSQL for v1 (matches the driver already vendored for the
app's own control-plane database); MySQL is modeled in DatabaseDialect for
forward-compat but rejected here until that driver is added — see
app.models.database_connection.

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


def build_engine(connection: DatabaseConnection) -> Engine:
    if connection.dialect != DatabaseDialect.POSTGRESQL:
        raise DatabaseOutputError(f"'{connection.dialect}' connections are not yet supported")
    url = (
        f"postgresql+psycopg://{connection.username}:{connection.password}"
        f"@{connection.host}:{connection.port}/{connection.database}"
    )
    return create_engine(url, connect_args={"connect_timeout": 5})


def test_connection(connection: DatabaseConnection) -> tuple[bool, str]:
    try:
        engine = build_engine(connection)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True, "Connected successfully"
    except DatabaseOutputError as exc:
        return False, str(exc)
    except SQLAlchemyError as exc:
        return False, str(exc.__cause__ or exc)


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
    table needs a fixed column set."""
    validate_identifier(table_name, "table_name")
    for field in fields:
        validate_identifier(field.name, "field name")

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
