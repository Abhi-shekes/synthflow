"""Phase 12 — MySQL and MongoDB push.

No real MySQL or MongoDB is guaranteed in the test environment, so these
cover the parts that are testable without one: dialect dispatch, URL
construction, value coercion, and the behaviour of the core install when
the optional driver is absent. Actual delivery is verified live against
real servers via the `mysql` and `mongo` compose profiles — see TODO.md,
the same split the Kafka and MQTT tests use.

The absent-driver half matters as much as the present-driver half: CI runs
this suite twice, once with no extras and once with all of them, so a
regression that makes `db_output` import pymongo at module scope fails the
core leg immediately.
"""

from types import SimpleNamespace

import pytest

from app.models.database_connection import DatabaseDialect
from app.models.field import FieldType
from app.services import db_output, install

requires_mysql = pytest.mark.skipif(
    not install.is_available("mysql"),
    reason="optional 'mysql' extra is not installed in this environment",
)
requires_mongo = pytest.mark.skipif(
    not install.is_available("mongo"),
    reason="optional 'mongo' extra is not installed in this environment",
)


def connection(dialect, **overrides):
    base = dict(
        dialect=dialect,
        host="db.example.com",
        port=5432,
        database="target",
        username="user",
        password="pass",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# URL construction
# --------------------------------------------------------------------------


def test_postgres_needs_no_optional_extra():
    """Its driver is already vendored for the app's own database, so a core
    install can still push to Postgres."""
    engine = db_output.build_engine(connection(DatabaseDialect.POSTGRESQL))
    assert engine.url.drivername == "postgresql+psycopg"


@requires_mysql
def test_mysql_url_uses_pymysql():
    engine = db_output.build_engine(connection(DatabaseDialect.MYSQL, port=3306))
    assert engine.url.drivername == "mysql+pymysql"
    assert engine.url.host == "db.example.com"
    assert engine.url.port == 3306


def test_credentials_are_url_encoded():
    """A password containing '@' or '/' would otherwise reshape the URL and
    surface as a baffling "unknown host" instead of an auth failure."""
    engine = db_output.build_engine(
        connection(DatabaseDialect.POSTGRESQL, username="user@corp", password="p@ss/w:rd")
    )
    assert engine.url.host == "db.example.com"
    # SQLAlchemy decodes them back, which is the proof they survived intact.
    assert engine.url.username == "user@corp"
    assert engine.url.password == "p@ss/w:rd"


def test_mongodb_has_no_sql_engine():
    """Asking for one is a programming error, not a user-facing condition —
    but it must fail clearly rather than build a nonsense URL."""
    with pytest.raises(db_output.DatabaseOutputError) as exc:
        db_output.build_engine(connection(DatabaseDialect.MONGODB))
    assert "not a SQL dialect" in str(exc.value)


# --------------------------------------------------------------------------
# Optional-driver behaviour
# --------------------------------------------------------------------------


def test_the_module_imports_without_either_optional_driver():
    """Guards the core leg of the CI matrix: a module-scope `import pymongo`
    would break every install that didn't ask for MongoDB."""
    assert hasattr(db_output, "push_rows")
    assert hasattr(db_output, "test_connection")


@pytest.mark.skipif(
    install.is_available("mongo"), reason="only meaningful without the 'mongo' extra"
)
def test_missing_driver_reports_how_to_install_it():
    ok, message = db_output.test_connection(connection(DatabaseDialect.MONGODB))
    assert ok is False
    assert "mongo" in message.lower()


# --------------------------------------------------------------------------
# Document coercion
# --------------------------------------------------------------------------


def test_structure_is_preserved_for_mongodb():
    """The SQL path serialises a list to a JSON string because a column
    can't hold one. Doing that in MongoDB would throw away the single thing
    a document store is for."""
    assert db_output._mongo_value(["a", "b"], FieldType.ARRAY) == ["a", "b"]
    assert db_output._mongo_value({"k": 1}, FieldType.OBJECT) == {"k": 1}


def test_structure_is_flattened_for_sql():
    assert db_output._coerce_value(["a", "b"], FieldType.ARRAY) == '["a", "b"]'


def test_a_date_stays_a_date_string_in_mongodb():
    """BSON has no date-only type, and silently promoting "2024-03-05" to a
    midnight timestamp invents a time zone question nobody asked."""
    assert db_output._mongo_value("2024-03-05", FieldType.DATE) == "2024-03-05"


def test_a_datetime_becomes_a_real_bson_datetime():
    """Unlike a date, a datetime has an unambiguous representation, and
    storing it as one is what makes range queries work."""
    value = db_output._mongo_value("2024-03-05T10:30:00", FieldType.DATETIME)
    assert value.year == 2024
    assert value.hour == 10


def test_nulls_survive_both_paths():
    assert db_output._mongo_value(None, FieldType.STRING) is None
    assert db_output._coerce_value(None, FieldType.STRING) is None


# --------------------------------------------------------------------------
# Identifier safety applies to every dialect
# --------------------------------------------------------------------------


@pytest.mark.parametrize("dialect", list(DatabaseDialect))
def test_unsafe_table_names_are_rejected_for_every_dialect(dialect):
    """MongoDB has no SQL injection surface, but a collection name is still
    validated: the check is about predictable, portable names, and making
    it dialect-dependent would be a rule nobody could remember."""
    fields = [SimpleNamespace(name="ok", field_type=FieldType.STRING, preset=None)]
    with pytest.raises(db_output.DatabaseOutputError):
        db_output.push_rows(connection(dialect), fields, [], "drop table users;--")
