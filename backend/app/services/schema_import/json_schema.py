"""Turn a JSON Schema or OpenAPI document into a `ProjectTemplate`.

These share one implementation because OpenAPI's `components.schemas`
*are* JSON Schema objects — so the OpenAPI path is really "find the
schemas, then run the JSON Schema importer over each one". Teams whose
source of truth is an API contract rather than a database get the same
result either way.

Scope worth being explicit about, since JSON Schema is far more
expressive than SynthFlow's field model:

- A nested object becomes its own entity, linked by a generated foreign
  key. That's the only honest mapping: SynthFlow entities are flat rows.
- `$ref` is resolved within the document. Remote refs are not fetched —
  reaching out over the network during an import is a surprise nobody
  asked for, so they're reported instead.
- `oneOf`/`anyOf`/`allOf` are not composed. The first branch is used and
  the rest reported, because guessing at a union would produce data that
  silently matches none of the branches.
"""

from typing import Any

from app.schemas.template import TemplateEntity, TemplateRelationship
from app.services.schema_import.common import (
    ImportResult,
    dedupe,
    empty_template,
    make_field,
    sanitize_identifier,
)


class JSONSchemaImportError(ValueError):
    pass


_JSON_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "json",
}

_FORMAT_MAP = {
    "date": "date",
    "date-time": "datetime",
    "uuid": "uuid",
    "email": "string",
}


def _resolve_ref(ref: str, root: dict[str, Any], result: ImportResult) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        result.warn(f"Remote $ref '{ref}' was not fetched — imports never make network calls")
        return None
    node: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            result.warn(f"$ref '{ref}' could not be resolved in this document")
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def _field_type_for(schema: dict[str, Any], path: str, result: ImportResult) -> str:
    fmt = schema.get("format")
    if isinstance(fmt, str) and fmt in _FORMAT_MAP:
        return _FORMAT_MAP[fmt]

    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        # ["string", "null"] is the common nullable idiom; the null is
        # already carried by the required-list, so take the other member.
        non_null = [t for t in raw_type if t != "null"]
        if len(non_null) > 1:
            result.warn(f"{path}: union type {raw_type} — imported as '{non_null[0]}'")
        raw_type = non_null[0] if non_null else "string"

    if schema.get("enum"):
        return "enum"

    if not isinstance(raw_type, str):
        result.warn(f"{path}: no type given, imported as 'string'")
        return "string"

    mapped = _JSON_TYPE_MAP.get(raw_type)
    if mapped is None:
        result.warn(f"{path}: unsupported type '{raw_type}', imported as 'string'")
        return "string"
    return mapped


def _import_object(
    name: str,
    schema: dict[str, Any],
    root: dict[str, Any],
    result: ImportResult,
    entity_names: set[str],
    path: str,
) -> str | None:
    """Create one entity from an object schema, recursing into nested
    objects. Returns the entity name, or None if there was nothing to
    import."""
    for combiner in ("oneOf", "anyOf", "allOf"):
        if combiner in schema:
            result.warn(
                f"{path}: '{combiner}' is not composed — the first branch was used and "
                f"the others ignored"
            )
            branches = schema[combiner]
            if isinstance(branches, list) and branches:
                merged = dict(schema)
                merged.pop(combiner)
                first = branches[0]
                if isinstance(first, dict):
                    merged.update(first)
                schema = merged
            break

    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], root, result)
        if resolved is None:
            return None
        schema = resolved

    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        result.warn(f"{path}: object has no properties, skipped")
        return None

    entity_name = dedupe(sanitize_identifier(name, fallback="entity"), entity_names)
    required = set(schema.get("required") or [])

    taken: set[str] = set()
    fields = []
    nested: list[tuple[str, dict[str, Any], str]] = []
    order = 0

    for raw_name, raw_schema in properties.items():
        if not isinstance(raw_schema, dict):
            continue
        prop_path = f"{path}.{raw_name}"

        prop_schema = raw_schema
        if "$ref" in prop_schema:
            resolved = _resolve_ref(prop_schema["$ref"], root, result)
            if resolved is None:
                continue
            prop_schema = resolved

        field_name = dedupe(sanitize_identifier(raw_name, fallback="field"), taken)
        if field_name != raw_name:
            result.warn(f"{prop_path}: renamed to '{field_name}'")

        # A nested object becomes its own entity rather than a blob,
        # so relationships and per-field rules still work on it.
        if prop_schema.get("type") == "object" and isinstance(prop_schema.get("properties"), dict):
            nested.append((raw_name, prop_schema, prop_path))
            continue

        field_type = _field_type_for(prop_schema, prop_path, result)
        enum_values = None
        if field_type == "enum":
            enum_values = [str(v) for v in (prop_schema.get("enum") or [])]
            if not enum_values:
                field_type = "string"

        minimum = prop_schema.get("minimum")
        maximum = prop_schema.get("maximum")

        fields.append(
            make_field(
                field_name,
                field_type,
                order=order,
                required=raw_name in required,
                nullable=raw_name not in required,
                min_value=float(minimum) if isinstance(minimum, (int, float)) else None,
                max_value=float(maximum) if isinstance(maximum, (int, float)) else None,
                enum_values=enum_values,
            )
        )
        order += 1

    if not fields and not nested:
        return None

    # Nested objects need a key on this entity to point at, and JSON has
    # no notion of one, so a synthetic id is added.
    if nested:
        id_name = dedupe("id", taken)
        fields.insert(
            0,
            make_field(id_name, "integer", order=0, required=True, nullable=False, unique=True),
        )
        for index, existing in enumerate(fields):
            existing.order = index

    result.template.entities.append(TemplateEntity(name=entity_name, fields=fields))

    for raw_name, nested_schema, nested_path in nested:
        child_name = _import_object(
            f"{name}_{raw_name}", nested_schema, root, result, entity_names, nested_path
        )
        if child_name is None:
            continue
        child = next(e for e in result.template.entities if e.name == child_name)
        fk_name = dedupe(f"{entity_name}_id", {f.name for f in child.fields})
        child.fields.append(
            make_field(
                fk_name,
                "integer",
                order=len(child.fields),
                required=True,
                nullable=False,
            )
        )
        result.template.relationships.append(
            TemplateRelationship(
                relationship_type="one_to_many",
                source_entity=child_name,
                source_field=fk_name,
                target_entity=entity_name,
                target_field=fields[0].name,
            )
        )
        result.warn(
            f"{nested_path}: nested object imported as its own entity "
            f"'{child_name}' linked by '{fk_name}' — SynthFlow entities are flat rows"
        )

    return entity_name


def import_from_json_schema(
    document: dict[str, Any],
    *,
    project_name: str | None = None,
) -> ImportResult:
    if not isinstance(document, dict):
        raise JSONSchemaImportError("Expected a JSON object.")

    is_openapi = "openapi" in document or "swagger" in document
    source = "OpenAPI document" if is_openapi else "JSON Schema"

    default_name = project_name
    if default_name is None:
        info = document.get("info") if isinstance(document.get("info"), dict) else {}
        default_name = info.get("title") or document.get("title") or "Imported schema"

    result = ImportResult(
        template=empty_template(str(default_name), description=f"Imported from a {source}.")
    )
    entity_names: set[str] = set()

    if is_openapi:
        components = document.get("components") or {}
        schemas = components.get("schemas") if isinstance(components, dict) else None
        if not isinstance(schemas, dict) or not schemas:
            raise JSONSchemaImportError(
                "No schemas found under components.schemas — SynthFlow imports the "
                "document's data models, not its paths."
            )
        for name, schema in schemas.items():
            if isinstance(schema, dict):
                _import_object(name, schema, document, result, entity_names, name)
    else:
        root_name = document.get("title") or "Record"
        # A top-level array schema describes a collection of its `items`.
        target = document
        if document.get("type") == "array" and isinstance(document.get("items"), dict):
            target = document["items"]
        _import_object(str(root_name), target, document, result, entity_names, str(root_name))

    if not result.template.entities:
        raise JSONSchemaImportError(
            "Nothing importable was found — SynthFlow needs at least one object "
            "schema with properties."
        )

    return result
