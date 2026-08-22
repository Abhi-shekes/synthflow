"""Shared pieces for every schema importer.

The organising decision for all of Phase 7: **an importer never creates
anything.** It reads some external description of a schema and returns a
`ProjectTemplate` — the same format `POST /projects/import` already
accepts from a hand-exported file. Applying it is a separate call the
user makes after looking at what came back.

That makes the roadmap's "mandatory review step" structural rather than a
UI convention: there is no code path from "read a database" to "rows in
the database", so a UI can't accidentally skip the review, and the import
half is Phase 5's already-proven all-or-nothing validation rather than a
second, parallel creation path that could drift from it.

The other half of an import result is `warnings`. Every importer is
lossy — SynthFlow has no concept of a check constraint, a composite
primary key, or a stored procedure — and silently dropping those would be
the worst outcome, because the project would look complete while quietly
meaning something different from the schema it came from. So anything
that couldn't be represented is reported by name.
"""

import keyword
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from app.schemas.template import ProjectTemplate, TemplateField, TemplateTrend

# SynthFlow entity and field names double as identifiers inside formulas
# and rules (`Customer.discount_rate`), so they have to be valid Python
# names for app.services.expressions to parse them.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NON_IDENTIFIER_CHARS = re.compile(r"[^A-Za-z0-9_]+")


@dataclass
class ImportResult:
    """A template plus everything that couldn't be carried across."""

    template: ProjectTemplate
    warnings: list[str] = dataclass_field(default_factory=list)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


def sanitize_identifier(raw: str, *, fallback: str = "field") -> str:
    """Turn an arbitrary column/table name into something usable as an
    identifier in an expression. Callers should warn when this changes
    the name, since the generated project will no longer match the source
    schema's spelling."""
    cleaned = _NON_IDENTIFIER_CHARS.sub("_", raw).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def is_clean_identifier(raw: str) -> bool:
    return bool(_IDENTIFIER_RE.match(raw)) and not keyword.iskeyword(raw)


def dedupe(name: str, taken: set[str]) -> str:
    """Entity and field names are the primary key of the template format,
    so collisions after sanitising have to be resolved, not tolerated."""
    if name not in taken:
        taken.add(name)
        return name
    index = 2
    while f"{name}_{index}" in taken:
        index += 1
    resolved = f"{name}_{index}"
    taken.add(resolved)
    return resolved


def make_field(
    name: str,
    field_type: str,
    *,
    order: int = 0,
    required: bool = False,
    nullable: bool = True,
    unique: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
    enum_values: list[str] | None = None,
    null_probability: float | None = None,
) -> TemplateField:
    """TemplateField has a lot of optional columns; importers only ever
    set a handful, so this keeps their call sites readable."""
    return TemplateField(
        name=name,
        field_type=field_type,
        order=order,
        required=required,
        nullable=nullable,
        unique=unique,
        min_value=min_value,
        max_value=max_value,
        enum_values=enum_values,
        null_probability=null_probability,
    )


def empty_template(name: str, description: str | None = None) -> ProjectTemplate:
    return ProjectTemplate(name=name, description=description)


# ---------------------------------------------------------------- types

# Matched against a lowercased SQL type name. Ordered longest-first at
# lookup time so "timestamp with time zone" beats "time", and
# "double precision" beats "double".
_SQL_TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("timestamp", "datetime"),
    ("datetime", "datetime"),
    ("date", "date"),
    ("time", "string"),
    ("uuid", "uuid"),
    ("boolean", "boolean"),
    ("bool", "boolean"),
    ("smallint", "integer"),
    ("bigint", "integer"),
    ("integer", "integer"),
    ("int", "integer"),
    ("serial", "integer"),
    ("decimal", "float"),
    ("numeric", "float"),
    ("double", "float"),
    ("real", "float"),
    ("float", "float"),
    ("money", "float"),
    ("jsonb", "json"),
    ("json", "json"),
    ("array", "array"),
    ("text", "string"),
    ("varchar", "string"),
    ("char", "string"),
    ("enum", "enum"),
)


def sql_type_to_field_type(sql_type: str) -> tuple[str, bool]:
    """Map a SQL type name onto a SynthFlow field type.

    Returns `(field_type, exact)`. `exact` is False when the mapping lost
    information the user should know about — a `TIME` column becoming a
    string, or an unrecognised type falling back to string — so the
    caller can turn that into a warning rather than the user discovering
    it when the data looks wrong.
    """
    lowered = sql_type.strip().lower()

    for pattern, mapped in sorted(_SQL_TYPE_PATTERNS, key=lambda p: -len(p[0])):
        if pattern in lowered:
            # TIME has no SynthFlow equivalent; it becomes a string.
            exact = not (pattern == "time" and "timestamp" not in lowered)
            return mapped, exact

    return "string", False


# Integer widths, used to give an imported column a sensible range rather
# than SynthFlow's default 0–100000, which would overflow a smallint.
INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "smallint": (0, 32_767),
    "int2": (0, 32_767),
    "integer": (0, 2_147_483_647),
    "int4": (0, 2_147_483_647),
    "int": (0, 2_147_483_647),
    "bigint": (0, 9_223_372_036_854_775_807),
    "int8": (0, 9_223_372_036_854_775_807),
}


def integer_range_for(sql_type: str) -> tuple[int, int] | None:
    lowered = sql_type.strip().lower()
    for name, bounds in INTEGER_RANGES.items():
        if lowered.startswith(name):
            return bounds
    return None


def autoincrement_trend(entity: str, field: str) -> TemplateTrend:
    """SynthFlow has no dedicated auto-increment flag — a linear trend with
    start=1, slope=1 on an integer field *is* a sequential counter, and is
    collision-free by construction (see ROADMAP Phase 2). Importers use
    this for SERIAL/IDENTITY/AUTO_INCREMENT columns so a generated primary
    key reads 1, 2, 3… instead of a random 216794, which is both more
    realistic and safe to insert back into the source schema.
    """
    return TemplateTrend(
        entity=entity,
        field=field,
        trend_type="linear",
        params={"start": 1, "slope": 1},
    )
