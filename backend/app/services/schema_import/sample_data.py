"""Infer a `ProjectTemplate` from a sample data file.

Parsing reuses `app.services.lookup_tables.parse_upload`, which already
handles CSV, Excel and JSON uploads for lookup tables — the file formats
are the same, only the intent differs, so a second parser would be two
things to keep in step.

What this does is deliberately shallow: per-column type inference, plus
observed ranges for numbers and observed values for low-cardinality
columns. It is *not* distribution fitting — a column of ages becomes
"integer between 18 and 94", not "normally distributed around 41".
Learning the actual shape of the data is Phase 9, and conflating the two
would make this phase's output look more faithful than it is.
"""

import re
from datetime import date, datetime
from typing import Any

from app.schemas.template import TemplateEntity
from app.services.lookup_tables import parse_upload
from app.services.schema_import.common import (
    ImportResult,
    dedupe,
    empty_template,
    make_field,
    sanitize_identifier,
)

# A column with at most this many distinct values, over at least this
# many rows, is treated as an enum rather than free text.
MAX_ENUM_VALUES = 12
MIN_ROWS_FOR_ENUM = 5

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


class SampleImportError(ValueError):
    pass


def _looks_like(values: list[str], pattern: re.Pattern[str]) -> bool:
    return bool(values) and all(pattern.match(v) for v in values)


def _infer_column(values: list[Any]) -> tuple[str, dict[str, Any]]:
    """Return (field_type, extras) for one column's observed values."""
    present = [v for v in values if v is not None and v != ""]
    if not present:
        return "string", {}

    if all(isinstance(v, bool) for v in present):
        return "boolean", {}

    if all(isinstance(v, int) and not isinstance(v, bool) for v in present):
        return "integer", {"min_value": float(min(present)), "max_value": float(max(present))}

    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "float", {"min_value": float(min(present)), "max_value": float(max(present))}

    if all(isinstance(v, dict) for v in present):
        return "json", {}
    if all(isinstance(v, list) for v in present):
        return "array", {}
    if all(isinstance(v, (date, datetime)) for v in present):
        kind = "datetime" if any(isinstance(v, datetime) for v in present) else "date"
        return kind, {}

    text = [str(v) for v in present]
    if _looks_like(text, _UUID_RE):
        return "uuid", {}
    if _looks_like(text, _DATETIME_RE):
        return "datetime", {}
    if _looks_like(text, _DATE_RE):
        return "date", {}

    distinct = sorted({t for t in text})
    if len(present) >= MIN_ROWS_FOR_ENUM and len(distinct) <= MAX_ENUM_VALUES:
        return "enum", {"enum_values": distinct}

    return "string", {}


def import_from_sample(
    filename: str,
    content: bytes,
    *,
    max_rows: int,
    entity_name: str | None = None,
    project_name: str | None = None,
) -> ImportResult:
    try:
        columns, rows = parse_upload(filename, content, max_rows)
    except ValueError as exc:
        raise SampleImportError(str(exc)) from exc

    if not columns:
        raise SampleImportError("No columns found in the file.")

    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0] or "Record"
    result = ImportResult(
        template=empty_template(
            project_name or f"{stem} (imported)",
            description=f"Inferred from a {len(rows)}-row sample of '{filename}'.",
        )
    )

    resolved_entity = sanitize_identifier(entity_name or stem, fallback="Record")
    taken: set[str] = set()
    fields = []

    for order, column in enumerate(columns):
        field_name = sanitize_identifier(column, fallback="column")
        if field_name != column:
            result.warn(f"Column '{column}': renamed to '{field_name}'")
        field_name = dedupe(field_name, taken)

        values = [row.get(column) for row in rows]
        field_type, extras = _infer_column(values)

        missing = sum(1 for v in values if v is None or v == "")
        distinct_present = {str(v) for v in values if v is not None and v != ""}
        non_missing = len(values) - missing
        is_unique = non_missing > 1 and len(distinct_present) == non_missing

        fields.append(
            make_field(
                field_name,
                field_type,
                order=order,
                required=missing == 0,
                nullable=missing > 0,
                unique=is_unique,
                **extras,
            )
        )

    result.template.entities.append(TemplateEntity(name=resolved_entity, fields=fields))

    result.warn(
        f"Types were inferred from {len(rows)} sample rows — ranges and enum values "
        f"reflect only what appeared in the sample, not the real distribution. "
        f"Fitting actual distributions is planned for a later phase."
    )
    if len(rows) < MIN_ROWS_FOR_ENUM:
        result.warn(
            f"Only {len(rows)} rows were available, which is too few to infer "
            f"low-cardinality columns as enums — they were imported as strings."
        )

    return result
