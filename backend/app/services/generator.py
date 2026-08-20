"""Batch generation engine: turns an Entity's field definitions into fake rows.

This is the Phase 1 "generate a batch of N rows" slice. It intentionally does not
know about relationships, rules, formulas, or state machines — those land in
Phase 2 as separate engines that compose with this one.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import exrex
from faker import Faker

from app.models.field import EntityField, FieldType

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


def generate_rows(fields: list[EntityField], count: int) -> list[dict[str, Any]]:
    seen_per_field: dict[str, set] = {f.name: set() for f in fields if f.unique}
    rows: list[dict[str, Any]] = []

    for _ in range(count):
        row: dict[str, Any] = {}
        for field in fields:
            if not field.required and field.nullable and random.random() < NULLABLE_PROBABILITY:
                row[field.name] = None
                continue

            if field.unique:
                row[field.name] = _generate_unique_value(field, seen_per_field[field.name])
            else:
                row[field.name] = _generate_value(field)
        rows.append(row)

    return rows
