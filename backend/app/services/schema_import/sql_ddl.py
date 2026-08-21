"""Turn a SQL DDL dump into a `ProjectTemplate`, with no live connection.

Parsing is delegated to `sqlglot` rather than hand-rolled with regexes.
SQL's grammar is genuinely hard — quoted identifiers, inline vs. trailing
constraints, dialect differences in `SERIAL`/`AUTO_INCREMENT`, comments
inside statements — and a regex parser would produce plausible-looking
wrong answers on real dumps, which is worse than failing. sqlglot is pure
Python with no compiled dependencies, so it doesn't complicate the image.

Statements that aren't `CREATE TABLE` (indexes, views, functions, inserts)
are skipped and reported rather than silently ignored, since a user
pasting a whole `pg_dump` should be told what wasn't used.
"""

import sqlglot
from sqlglot import exp

from app.schemas.template import TemplateEntity, TemplateRelationship
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


class SQLImportError(ValueError):
    pass


def _table_name(table: exp.Table | exp.Schema | None) -> str | None:
    if table is None:
        return None
    if isinstance(table, exp.Schema):
        table = table.this
    if isinstance(table, exp.Table):
        return table.name
    return None


def import_from_sql(
    ddl: str,
    *,
    dialect: str | None = None,
    project_name: str | None = None,
) -> ImportResult:
    if not ddl.strip():
        raise SQLImportError("No SQL provided.")

    try:
        statements = sqlglot.parse(ddl, read=dialect or None)
    except Exception as exc:
        raise SQLImportError(f"Could not parse the SQL: {exc}") from exc

    result = ImportResult(
        template=empty_template(
            project_name or "Imported schema",
            description="Imported from a SQL DDL script.",
        )
    )

    entity_names: set[str] = set()
    entity_by_table: dict[str, str] = {}
    field_by_column: dict[tuple[str, str], str] = {}
    # Deferred so every table exists before foreign keys are resolved.
    pending_fks: list[tuple[str, str, str, str]] = []
    skipped_kinds: set[str] = set()

    for statement in statements:
        if statement is None:
            continue
        if not isinstance(statement, exp.Create) or (statement.args.get("kind") or "").upper() != (
            "TABLE"
        ):
            kind = type(statement).__name__
            if isinstance(statement, exp.Create):
                kind = f"CREATE {(statement.args.get('kind') or '?').upper()}"
            skipped_kinds.add(kind)
            continue

        table = _table_name(statement.this)
        if not table:
            continue

        entity_name = sanitize_identifier(table, fallback="entity")
        if entity_name != table:
            result.warn(f"Table '{table}': imported as entity '{entity_name}'")
        entity_name = dedupe(entity_name, entity_names)
        entity_by_table[table] = entity_name

        schema = statement.this if isinstance(statement.this, exp.Schema) else None
        definitions = list(schema.expressions) if schema is not None else []

        unique_columns: set[str] = set()
        primary_keys: set[str] = set()

        # Table-level constraints come through as siblings of the columns.
        for definition in definitions:
            if isinstance(definition, exp.PrimaryKey):
                for column in definition.expressions:
                    primary_keys.add(column.name if hasattr(column, "name") else str(column))
            elif isinstance(definition, exp.UniqueColumnConstraint):
                for column in definition.find_all(exp.Column):
                    unique_columns.add(column.name)
            elif isinstance(definition, exp.ForeignKey):
                source_cols = [c.name for c in definition.expressions]
                reference = definition.args.get("reference")
                target_table = None
                target_cols: list[str] = []
                if reference is not None:
                    target_schema = reference.this
                    target_table = _table_name(target_schema)
                    if isinstance(target_schema, exp.Schema):
                        target_cols = [c.name for c in target_schema.expressions]
                if len(source_cols) == 1 and len(target_cols) == 1 and target_table:
                    pending_fks.append((table, source_cols[0], target_table, target_cols[0]))
                elif source_cols:
                    result.warn(
                        f"Table '{table}': composite foreign key "
                        f"({', '.join(source_cols)}) not imported — SynthFlow "
                        f"relationships link exactly one field to one field"
                    )
            elif isinstance(definition, exp.CheckColumnConstraint):
                result.warn(
                    f"Table '{table}': CHECK constraint not imported — express it as "
                    f"a rule on the entity instead"
                )

        taken_fields: set[str] = set()
        fields = []
        autoincrement_fields: list[str] = []
        order = 0
        for definition in definitions:
            if not isinstance(definition, exp.ColumnDef):
                continue

            raw_name = definition.name
            name = sanitize_identifier(raw_name, fallback="column")
            if name != raw_name:
                result.warn(f"{table}.{raw_name}: renamed to '{name}'")
            name = dedupe(name, taken_fields)

            sql_type = definition.args.get("kind")
            sql_type_text = sql_type.sql() if sql_type is not None else "text"
            field_type, exact = sql_type_to_field_type(sql_type_text)
            if not exact:
                result.warn(
                    f"{table}.{raw_name}: SQL type '{sql_type_text}' has no exact "
                    f"SynthFlow equivalent, imported as '{field_type}'"
                )

            nullable = True
            is_unique = raw_name in unique_columns or raw_name in primary_keys
            for constraint in definition.constraints:
                kind = constraint.kind
                if isinstance(kind, exp.NotNullColumnConstraint):
                    # sqlglot models both NOT NULL and an explicit NULL with
                    # this node: `allow_null` is set only for the latter. So
                    # the column is nullable exactly when allow_null is true,
                    # not the other way round.
                    nullable = bool(kind.args.get("allow_null", False))
                elif isinstance(kind, exp.Reference):
                    # An inline `REFERENCES other(col)`, as opposed to a
                    # table-level FOREIGN KEY handled above. Both are common
                    # in real dumps and only supporting one silently loses
                    # half the relationships.
                    ref_schema = kind.this
                    ref_table = _table_name(ref_schema)
                    ref_cols = (
                        [c.name for c in ref_schema.expressions]
                        if isinstance(ref_schema, exp.Schema)
                        else []
                    )
                    if ref_table and len(ref_cols) == 1:
                        pending_fks.append((table, raw_name, ref_table, ref_cols[0]))
                    elif ref_table:
                        result.warn(
                            f"{table}.{raw_name}: REFERENCES {ref_table} without a "
                            f"single named column was not imported"
                        )
                elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
                    is_unique = True
                    nullable = False
                elif isinstance(kind, exp.UniqueColumnConstraint):
                    is_unique = True
                elif isinstance(kind, exp.CheckColumnConstraint):
                    result.warn(
                        f"{table}.{raw_name}: CHECK constraint not imported — express "
                        f"it as a rule on the entity instead"
                    )

            # SERIAL/BIGSERIAL are types; IDENTITY and AUTO_INCREMENT arrive
            # as column constraints. Cover both so an imported key is a
            # counter regardless of which dialect wrote the DDL.
            is_autoincrement = "serial" in sql_type_text.lower() or any(
                type(c.kind).__name__
                in ("GeneratedAsIdentityColumnConstraint", "AutoIncrementColumnConstraint")
                for c in definition.constraints
            )

            min_value = max_value = None
            if field_type == "integer":
                bounds = integer_range_for(sql_type_text)
                if bounds is not None:
                    min_value, max_value = (0, min(bounds[1], 1_000_000))

            fields.append(
                make_field(
                    name,
                    field_type,
                    order=order,
                    required=not nullable,
                    nullable=nullable,
                    unique=is_unique,
                    min_value=min_value,
                    max_value=max_value,
                )
            )
            field_by_column[(table, raw_name)] = name
            if is_autoincrement and field_type == "integer":
                autoincrement_fields.append(name)
            order += 1

        if not fields:
            result.warn(f"Table '{table}': no columns parsed, skipped")
            entity_by_table.pop(table, None)
            continue

        result.template.entities.append(TemplateEntity(name=entity_name, fields=fields))
        for field_name in autoincrement_fields:
            result.template.trends.append(autoincrement_trend(entity_name, field_name))

    if not result.template.entities:
        raise SQLImportError("No CREATE TABLE statements found in the SQL.")

    for source_table, source_col, target_table, target_col in pending_fks:
        if target_table not in entity_by_table:
            result.warn(
                f"Table '{source_table}': foreign key to '{target_table}' skipped — "
                f"no CREATE TABLE for it in this script"
            )
            continue
        if source_table == target_table:
            result.warn(
                f"Table '{source_table}': self-referencing foreign key not imported — "
                f"SynthFlow relationships must connect two different entities"
            )
            continue
        source_field = field_by_column.get((source_table, source_col))
        target_field = field_by_column.get((target_table, target_col))
        if source_field is None or target_field is None:
            continue
        result.template.relationships.append(
            TemplateRelationship(
                relationship_type="one_to_many",
                source_entity=entity_by_table[source_table],
                source_field=source_field,
                target_entity=entity_by_table[target_table],
                target_field=target_field,
            )
        )

    if skipped_kinds:
        result.warn("Ignored non-table statements: " + ", ".join(sorted(skipped_kinds)))

    return result
