"""Batch generation engine: turns Entity field definitions into fake rows.

Phase 1 covers a single entity in isolation. Phase 2 adds `generate_project`,
which generates every entity in a project in relationship-dependency order so a
child entity's foreign-key field draws real values from its already-generated
parent instead of being randomized independently. Rules, formulas, and state
machines are still later phases.
"""

import csv
import io
import json
import random
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import exrex
from faker import Faker

from app.models.entity import Entity
from app.models.field import EntityField, FieldType
from app.models.relationship import Relationship

faker = Faker()

NULLABLE_PROBABILITY = 0.15
MAX_UNIQUE_ATTEMPTS = 100


def _generate_value(field: EntityField) -> Any:
    if field.field_type == FieldType.STRING:
        if field.regex:
            return exrex.getone(field.regex)
        return faker.word()

    if field.field_type == FieldType.INTEGER:
        low = int(field.min_value) if field.min_value is not None else 0
        high = int(field.max_value) if field.max_value is not None else 100_000
        return random.randint(low, high)

    if field.field_type == FieldType.FLOAT:
        low = field.min_value if field.min_value is not None else 0.0
        high = field.max_value if field.max_value is not None else 100_000.0
        return round(random.uniform(low, high), 2)

    if field.field_type == FieldType.BOOLEAN:
        return faker.boolean()

    if field.field_type == FieldType.DATE:
        start = datetime.now(UTC).date() - timedelta(days=365)
        return faker.date_between(start_date=start, end_date="today").isoformat()

    if field.field_type == FieldType.DATETIME:
        start = datetime.now(UTC) - timedelta(days=365)
        return faker.date_time_between(start_date=start, end_date="now").isoformat()

    if field.field_type == FieldType.UUID:
        return str(uuid.uuid4())

    if field.field_type == FieldType.ENUM:
        if not field.enum_values:
            raise ValueError(f"Field '{field.name}' is type enum but has no enum_values")
        return random.choice(field.enum_values)

    if field.field_type == FieldType.ARRAY:
        return [faker.word() for _ in range(random.randint(1, 3))]

    if field.field_type in (FieldType.OBJECT, FieldType.JSON):
        return {faker.word(): faker.word() for _ in range(random.randint(1, 3))}

    raise ValueError(f"Unsupported field type: {field.field_type}")


def _generate_unique_value(field: EntityField, seen: set) -> Any:
    for _ in range(MAX_UNIQUE_ATTEMPTS):
        value = _generate_value(field)
        key = str(value)
        if key not in seen:
            seen.add(key)
            return value
    raise ValueError(
        f"Could not generate a unique value for field '{field.name}' "
        f"after {MAX_UNIQUE_ATTEMPTS} attempts"
    )


def generate_rows(
    fields: list[EntityField],
    count: int,
    fk_pools: dict[str, list[Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate `count` rows for `fields`. `fk_pools` maps a field name to a pool
    of real values (typically another entity's already-generated column) to draw
    from instead of randomizing that field independently — this is how
    relationships are enforced at generation time. A pool field marked `unique`
    is drawn without replacement; otherwise values are drawn with replacement."""
    fk_pools = fk_pools or {}
    seen_per_field: dict[str, set] = {
        f.name: set() for f in fields if f.unique and f.name not in fk_pools
    }
    unique_fk_queues: dict[str, list[Any]] = {}
    for field in fields:
        if field.name in fk_pools and field.unique:
            queue = list(fk_pools[field.name])
            random.shuffle(queue)
            unique_fk_queues[field.name] = queue

    rows: list[dict[str, Any]] = []
    for _ in range(count):
        row: dict[str, Any] = {}
        for field in fields:
            if not field.required and field.nullable and random.random() < NULLABLE_PROBABILITY:
                row[field.name] = None
                continue

            if field.name in fk_pools:
                if field.unique:
                    queue = unique_fk_queues[field.name]
                    if not queue:
                        raise ValueError(
                            f"Field '{field.name}' is unique and ran out of distinct values "
                            "from the referenced entity"
                        )
                    row[field.name] = queue.pop()
                else:
                    row[field.name] = random.choice(fk_pools[field.name])
            elif field.unique:
                row[field.name] = _generate_unique_value(field, seen_per_field[field.name])
            else:
                row[field.name] = _generate_value(field)
        rows.append(row)

    return rows


def _topological_order(graph: dict[uuid.UUID, Iterable[uuid.UUID]]) -> list[uuid.UUID]:
    """Postorder DFS topological sort: `graph[node]` is the set of nodes that must
    come before `node`. Raises ValueError on a cycle."""
    state: dict[uuid.UUID, str] = {}
    order: list[uuid.UUID] = []

    def visit(node: uuid.UUID) -> None:
        if state.get(node) == "done":
            return
        if state.get(node) == "visiting":
            raise ValueError("Circular relationship detected between entities")
        state[node] = "visiting"
        for dep in graph.get(node, ()):
            visit(dep)
        state[node] = "done"
        order.append(node)

    for node in graph:
        visit(node)

    return order


def generate_project(
    entities: list[Entity],
    relationships: list[Relationship],
    counts: dict[uuid.UUID, int],
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Generate every entity in a project, honoring relationships: a source
    entity's foreign-key field is populated from its target entity's
    already-generated rows, so targets are always generated before their
    sources (dependency order via topological sort over the relationship
    graph)."""
    entities_by_id = {e.id: e for e in entities}
    fields_by_id = {f.id: f for e in entities for f in e.fields}

    graph: dict[uuid.UUID, set[uuid.UUID]] = {e.id: set() for e in entities}
    relationships_by_source: dict[uuid.UUID, list[Relationship]] = {}
    for rel in relationships:
        graph.setdefault(rel.source_entity_id, set()).add(rel.target_entity_id)
        relationships_by_source.setdefault(rel.source_entity_id, []).append(rel)

    order = _topological_order(graph)

    generated: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for entity_id in order:
        entity = entities_by_id.get(entity_id)
        if entity is None or not entity.fields:
            generated[entity_id] = []
            continue

        fk_pools: dict[str, list[Any]] = {}
        for rel in relationships_by_source.get(entity_id, []):
            target_field = fields_by_id[rel.target_field_id]
            source_field = fields_by_id[rel.source_field_id]
            target_rows = generated.get(rel.target_entity_id, [])
            pool = [
                row[target_field.name]
                for row in target_rows
                if row.get(target_field.name) is not None
            ]
            if not pool:
                target_entity = entities_by_id[rel.target_entity_id]
                raise ValueError(
                    f"Cannot generate '{entity.name}.{source_field.name}': "
                    f"'{target_entity.name}.{target_field.name}' has no generated values "
                    "to reference (check that entity has fields and a non-zero count)"
                )
            fk_pools[source_field.name] = pool

        generated[entity_id] = generate_rows(entity.fields, counts.get(entity_id, 10), fk_pools)

    return generated


def rows_to_csv(fields: list[EntityField], rows: list[dict[str, Any]]) -> str:
    fieldnames = [f.name for f in fields]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                name: json.dumps(value) if isinstance(value, (list, dict)) else value
                for name, value in row.items()
            }
        )
    return buffer.getvalue()
