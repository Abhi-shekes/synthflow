"""Turn a live database's schema into a `ProjectTemplate`.

Uses SQLAlchemy's `inspect()` rather than querying `information_schema`
by hand, which means the dialect handles the differences and adding
MySQL later is a connection-string change rather than a second
implementation. Connection setup reuses `app.services.db_output`, so
importing *from* a database and pushing *to* one share the same
credentials model, timeout and dialect gate.

Read-only by construction: only the inspector is used, no queries are
issued against table contents, and nothing here writes.
"""

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.models.database_connection import DatabaseConnection
from app.schemas.template import TemplateEntity, TemplateRelationship
from app.services.db_output import DatabaseOutputError, build_engine
from app.services.schema_import.common import (
    ImportResult,
    autoincrement_trend,
    dedupe,
    empty_template,
    integer_range_for,
    make_field,
    sanitize_identifier,
    sql_type_to_field_type,
)


def _column_to_field(
    column: dict[str, Any],
    order: int,
    *,
    table: str,
    primary_keys: set[str],
    unique_columns: set[str],
    result: ImportResult,
    taken: set[str],
) -> Any:
    raw_name = column["name"]
    name = sanitize_identifier(raw_name, fallback="column")
    if name != raw_name:
        result.warn(
            f"{table}.{raw_name}: renamed to '{name}' so it can be referenced in formulas and rules"
        )
    name = dedupe(name, taken)

    sql_type = str(column.get("type", "")) or "text"
    field_type, exact = sql_type_to_field_type(sql_type)
    if not exact:
        result.warn(
            f"{table}.{raw_name}: SQL type '{sql_type}' has no exact SynthFlow "
            f"equivalent, imported as '{field_type}'"
        )

    nullable = bool(column.get("nullable", True))
    is_unique = raw_name in unique_columns or raw_name in primary_keys

    min_value: float | None = None
    max_value: float | None = None
    if field_type == "integer":
        bounds = integer_range_for(sql_type)
        if bounds is not None:
            # Cap the default range to the column's real width, so an
            # imported smallint doesn't immediately generate values that
            # would fail to insert back into the source schema.
            min_value, max_value = (0, min(bounds[1], 1_000_000))

    return make_field(
        name,
        field_type,
        order=order,
        required=not nullable,
        nullable=nullable,
        unique=is_unique,
        min_value=min_value,
        max_value=max_value,
    )


def import_from_database(
    connection: DatabaseConnection,
    *,
    project_name: str | None = None,
    schema: str | None = None,
) -> ImportResult:
    """Introspect `connection` and return a template. Raises
    DatabaseOutputError for anything connection-related, which the route
    turns into a 400."""
    engine = build_engine(connection)

    result = ImportResult(
        template=empty_template(
            project_name or f"{connection.database} (imported)",
            description=f"Imported from {connection.dialect} database "
            f"'{connection.database}' on {connection.host}.",
        )
    )

    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names(schema=schema)

            if not table_names:
                raise DatabaseOutputError("No tables found — check the database and schema name.")

            entity_names: set[str] = set()
            # Maps the source table name to the entity name it became, so
            # foreign keys can be resolved after every table is known.
            entity_by_table: dict[str, str] = {}
            # (table, column) -> field name, same reason.
            field_by_column: dict[tuple[str, str], str] = {}

            for table in sorted(table_names):
                entity_name = sanitize_identifier(table, fallback="entity")
                if entity_name != table:
                    result.warn(f"Table '{table}': imported as entity '{entity_name}'")
                entity_name = dedupe(entity_name, entity_names)
                entity_by_table[table] = entity_name

                pk = inspector.get_pk_constraint(table, schema=schema) or {}
                primary_keys = set(pk.get("constrained_columns") or [])
                if len(primary_keys) > 1:
                    result.warn(
                        f"Table '{table}': composite primary key "
                        f"({', '.join(sorted(primary_keys))}) — SynthFlow has no "
                        f"composite key concept, each column was marked unique "
                        f"individually, which is stricter than the original"
                    )

                unique_columns: set[str] = set()
                for constraint in inspector.get_unique_constraints(table, schema=schema) or []:
                    columns = constraint.get("column_names") or []
                    if len(columns) == 1:
                        unique_columns.add(columns[0])
                    elif columns:
                        result.warn(
                            f"Table '{table}': multi-column unique constraint "
                            f"({', '.join(columns)}) not imported — SynthFlow can only "
                            f"enforce uniqueness per field"
                        )

                for check in inspector.get_check_constraints(table, schema=schema) or []:
                    result.warn(
                        f"Table '{table}': check constraint "
                        f"'{check.get('name') or 'unnamed'}' not imported — express it "
                        f"as a rule on the entity instead"
                    )

                taken_fields: set[str] = set()
                fields = []
                autoincrement_fields: list[str] = []
                for order, column in enumerate(inspector.get_columns(table, schema=schema)):
                    field = _column_to_field(
                        column,
                        order,
                        table=table,
                        primary_keys=primary_keys,
                        unique_columns=unique_columns,
                        result=result,
                        taken=taken_fields,
                    )
                    fields.append(field)
                    field_by_column[(table, column["name"])] = field.name
                    if column.get("autoincrement") and field.field_type == "integer":
                        autoincrement_fields.append(field.name)

                if not fields:
                    result.warn(f"Table '{table}': no columns found, skipped")
                    continue

                result.template.entities.append(TemplateEntity(name=entity_name, fields=fields))
                for field_name in autoincrement_fields:
                    result.template.trends.append(autoincrement_trend(entity_name, field_name))

            _add_relationships(
                inspector,
                schema,
                table_names,
                entity_by_table,
                field_by_column,
                result,
            )

    except DatabaseOutputError:
        raise
    except SQLAlchemyError as exc:
        raise DatabaseOutputError(str(exc.__cause__ or exc)) from exc
    finally:
        engine.dispose()

    return result


def _add_relationships(
    inspector: Any,
    schema: str | None,
    table_names: list[str],
    entity_by_table: dict[str, str],
    field_by_column: dict[tuple[str, str], str],
    result: ImportResult,
) -> None:
    for table in sorted(table_names):
        if table not in entity_by_table:
            continue
        for fk in inspector.get_foreign_keys(table, schema=schema) or []:
            target_table = fk.get("referred_table")
            source_columns = fk.get("constrained_columns") or []
            target_columns = fk.get("referred_columns") or []

            if not target_table or target_table not in entity_by_table:
                result.warn(
                    f"Table '{table}': foreign key to '{target_table}' skipped — "
                    f"that table wasn't part of this import"
                )
                continue

            if len(source_columns) != 1 or len(target_columns) != 1:
                result.warn(
                    f"Table '{table}': composite foreign key "
                    f"({', '.join(source_columns)}) not imported — SynthFlow "
                    f"relationships link exactly one field to one field"
                )
                continue

            if table == target_table:
                result.warn(
                    f"Table '{table}': self-referencing foreign key not imported — "
                    f"SynthFlow relationships must connect two different entities"
                )
                continue

            source_field = field_by_column.get((table, source_columns[0]))
            target_field = field_by_column.get((target_table, target_columns[0]))
            if source_field is None or target_field is None:
                continue

            result.template.relationships.append(
                TemplateRelationship(
                    relationship_type="one_to_many",
                    source_entity=entity_by_table[table],
                    source_field=source_field,
                    target_entity=entity_by_table[target_table],
                    target_field=target_field,
                )
            )
