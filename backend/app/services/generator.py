"""Batch generation engine: turns Entity field definitions into fake rows.

Phase 1 covers a single entity in isolation. Phase 2 adds `generate_project`
(entities generated in relationship-dependency order so a child's foreign-key
field draws real values from its already-generated parent), formula fields
(a field's value computed from other fields on the same row instead of being
randomized), rules (a boolean expression a generated row must satisfy,
enforced by discard-and-retry), and workflows (a field's value comes from a
random walk over a state machine instead of being randomized independently).
Phase 4 adds trends (a numeric field's value as a function of its row's
position within the current batch — see app.models.trend.Trend) and weighted
enum fields (app.models.field.EntityField.enum_weights).
"""

import csv
import io
import json
import random
import re
import uuid
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import exrex
from faker import Faker
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.models.entity import Entity
from app.models.error_injection import ErrorInjection, ErrorType
from app.models.event_trigger import EventTrigger
from app.models.field import EntityField, FieldType
from app.models.lookup_attachment import LookupAttachment
from app.models.relationship import Relationship
from app.models.rule import Rule
from app.models.trend import Trend
from app.models.workflow import Workflow
from app.services.expressions import ExpressionError, evaluate
from app.services.log_generators import generate_log_line
from app.services.lookup_tables import coerce_numeric
from app.services.trends import generate_trend_value

faker = Faker()

NULLABLE_PROBABILITY = 0.15
MAX_UNIQUE_ATTEMPTS = 100
MAX_RULE_ATTEMPTS = 200
MAX_WORKFLOW_STEPS = 20
WORKFLOW_STOP_PROBABILITY = 0.35


def _generate_value(field: EntityField) -> Any:
    if field.field_type == FieldType.STRING:
        if field.preset:
            return generate_log_line(field.preset)
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
        if field.enum_weights:
            chosen = random.choices(field.enum_values, weights=field.enum_weights, k=1)[0]
        else:
            chosen = random.choice(field.enum_values)
        # enum_values are always configured as strings (see EntityField), but
        # a numeric-looking one — e.g. a weighted HTTP status code enum
        # ("200", "404", "500") for API-behavior simulation — should come out
        # as a real int/float in generated output, not stay a string.
        return coerce_numeric(chosen)

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


def build_lookup_pools(attachments: list[LookupAttachment]) -> dict[str, list[Any]]:
    """Builds a field-name -> value-pool dict from each attachment's lookup
    table column, in the exact shape `generate_rows` already expects for
    relationship-sourced `fk_pools` — a lookup-attached field is drawn from
    this pool the same way a foreign-key field is, including honoring
    `field.unique` for without-replacement draws (see `_generate_one_row`).
    Rows missing the column, or holding a null there, are skipped."""
    pools: dict[str, list[Any]] = {}
    for attachment in attachments:
        values = [
            row[attachment.column]
            for row in attachment.lookup_table.data
            if row.get(attachment.column) is not None
        ]
        if not values:
            raise ValueError(
                f"Lookup table '{attachment.lookup_table.name}' has no non-null values "
                f"in column '{attachment.column}'"
            )
        pools[attachment.field.name] = values
    return pools


def _evaluate_formula(field: EntityField, row_so_far: dict[str, Any]) -> Any:
    try:
        return evaluate(field.formula, row_so_far)
    except ExpressionError as exc:
        raise ValueError(f"Formula for field '{field.name}' failed: {exc}") from exc


def _row_satisfies_rules(row: dict[str, Any], rules: list[Rule]) -> bool:
    for rule in rules:
        try:
            if not evaluate(rule.condition, row):
                return False
        except ExpressionError as exc:
            raise ValueError(f"Rule '{rule.condition}' failed to evaluate: {exc}") from exc
    return True


def _evaluate_event_triggers(
    row: dict[str, Any], event_triggers: list[EventTrigger]
) -> list[str]:
    """Unlike a rule, a matching trigger doesn't reject the row — it collects
    labels for `_triggered_events`. See EventTrigger's docstring for why
    that's the whole feature for now (no external notification fires)."""
    triggered: list[str] = []
    for trigger in event_triggers:
        try:
            if evaluate(trigger.condition, row):
                triggered.append(trigger.label)
        except ExpressionError as exc:
            raise ValueError(
                f"Event trigger '{trigger.label}' failed to evaluate: {exc}"
            ) from exc
    return triggered


def _generate_state_walk(workflow: Workflow) -> list[str]:
    """A random walk through the workflow's transition graph, starting from a
    random initial state and stopping (with WORKFLOW_STOP_PROBABILITY chance
    per step, or when a state has no outgoing transitions) within
    MAX_WORKFLOW_STEPS hops. Later states are naturally rarer since they
    require surviving more consecutive "don't stop" draws — a deliberate,
    simple stand-in for "most records are further along than not yet started,
    but few reach the very end," not a claim about any real-world process."""
    if not workflow.initial_states:
        raise ValueError("Workflow has no initial states")

    by_source: dict[str, list[str]] = {}
    for t in workflow.transitions:
        by_source.setdefault(t["source"], []).append(t["target"])

    path = [random.choice(workflow.initial_states)]
    for _ in range(MAX_WORKFLOW_STEPS - 1):
        options = by_source.get(path[-1], [])
        if not options or random.random() < WORKFLOW_STOP_PROBABILITY:
            break
        path.append(random.choice(options))
    return path


def _corrupt_value(
    value: Any,
    field: EntityField,
    error_types: list[str],
    previous_row: dict[str, Any] | None,
) -> Any:
    """Replaces an already-computed field value with a deliberately bad one.
    Picks one enabled error type at random per corrupted row, so a field with
    several configured types produces a mix of failure modes across a batch
    rather than always the same one. See app.models.error_injection for the
    full design, including the documented rules interaction."""
    error_type = random.choice(error_types)

    if error_type == ErrorType.NULL:
        return None

    if error_type == ErrorType.EMPTY:
        if field.field_type == FieldType.STRING:
            return ""
        if field.field_type == FieldType.ARRAY:
            return []
        return {}

    if error_type == ErrorType.DUPLICATE:
        if previous_row is not None and field.name in previous_row:
            return previous_row[field.name]
        return value

    if error_type == ErrorType.TRUNCATE:
        text = str(value)
        if len(text) <= 1:
            return text
        return text[: random.randint(1, len(text) - 1)]

    if error_type == ErrorType.WRONG_TYPE:
        if field.field_type in (FieldType.INTEGER, FieldType.FLOAT):
            return faker.word()
        return faker.random_int(min=0, max=999_999)

    if error_type == ErrorType.OUT_OF_RANGE:
        if field.field_type == FieldType.INTEGER:
            low = int(field.min_value) if field.min_value is not None else 0
            high = int(field.max_value) if field.max_value is not None else 100_000
            offset = random.randint(1, 1_000)
            return random.choice([low - offset, high + offset])
        low = field.min_value if field.min_value is not None else 0.0
        high = field.max_value if field.max_value is not None else 100_000.0
        offset = random.uniform(1, 1_000)
        return random.choice([low - offset, high + offset])

    return value


def _generate_one_row(
    fields: list[EntityField],
    fk_pools: dict[str, list[Any]],
    seen_per_field: dict[str, set],
    unique_fk_queues: dict[str, list[Any]],
    workflows: dict[str, Workflow],
    trends: dict[str, Trend],
    trend_state: dict[str, dict],
    error_injections: dict[str, ErrorInjection],
    previous_row: dict[str, Any] | None,
    position: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field in fields:
        workflow_path: list[str] | None = None

        if field.formula:
            value = _evaluate_formula(field, row)
        elif field.name in trends:
            raw = generate_trend_value(trends[field.name], position, trend_state[field.name])
            value = round(raw) if field.field_type == FieldType.INTEGER else round(raw, 2)
        elif field.name in workflows:
            workflow_path = _generate_state_walk(workflows[field.name])
            value = workflow_path[-1]
        elif not field.required and field.nullable and random.random() < NULLABLE_PROBABILITY:
            value = None
        elif field.name in fk_pools:
            if field.unique:
                queue = unique_fk_queues[field.name]
                if not queue:
                    raise ValueError(
                        f"Field '{field.name}' is unique and ran out of distinct values "
                        "in its pool (relationship or lookup table)"
                    )
                value = queue.pop()
            else:
                value = random.choice(fk_pools[field.name])
        elif field.unique:
            value = _generate_unique_value(field, seen_per_field[field.name])
        else:
            value = _generate_value(field)

        injection = error_injections.get(field.name)
        if injection is not None and random.random() < injection.rate:
            value = _corrupt_value(value, field, injection.error_types, previous_row)

        row[field.name] = value
        if workflow_path is not None:
            row[f"{field.name}_history"] = workflow_path
    return row


def generate_rows(
    fields: list[EntityField],
    count: int,
    fk_pools: dict[str, list[Any]] | None = None,
    rules: list[Rule] | None = None,
    workflows: list[Workflow] | None = None,
    trends: list[Trend] | None = None,
    error_injections: list[ErrorInjection] | None = None,
    event_triggers: list[EventTrigger] | None = None,
) -> list[dict[str, Any]]:
    """Generate `count` rows for `fields`.

    `fk_pools` maps a field name to a pool of real values to draw from instead
    of randomizing that field independently — this is how both relationships
    and lookup tables are enforced at generation time (see
    build_lookup_pools; a relationship's caller builds this dict from another
    entity's already-generated column the same way). A pool field marked
    `unique` is drawn without replacement; otherwise values are drawn with
    replacement.

    `rules` are boolean expressions a finished row must satisfy; a row that
    fails one is discarded and regenerated (bounded retries). A discarded
    row's values are not "returned" to unique pools/seen-sets, so rules that
    reject a lot of candidates can exhaust a small unique pool faster than the
    requested `count` would otherwise need — a known tradeoff, not a bug.

    `workflows` are state machines attached to a field; that field's value
    comes from a random walk over the graph (see _generate_state_walk)
    instead of the type-based generator, and the walk itself is exposed
    alongside it as `<field>_history`.

    `trends` make a numeric field's value a function of its row's 0-indexed
    position within this call's batch (see app.services.trends) instead of
    an independent random draw — position always starts at 0 here, so a
    trend replays from its start every `generate_rows` call rather than
    continuing across calls (see Trend's docstring for what that means for a
    WebSocket stream's repeated ticks).

    `error_injections` deliberately corrupt a field's value on some fraction
    of rows, after that value is otherwise fully computed (see
    app.models.error_injection and _corrupt_value). Because corruption runs
    before rule-checking, a rule constraining the same field can discard and
    regenerate the very rows error injection was meant to produce — see the
    ErrorInjection model docstring for that tradeoff.

    `event_triggers` are boolean expressions evaluated against each *kept*
    row (after it has already passed every rule); every trigger that matches
    has its `label` appended to that row's `_triggered_events` list, added
    only when at least one trigger is configured (see EventTrigger's
    docstring — this doesn't discard the row or send anything externally).
    """
    fk_pools = fk_pools or {}
    rules = rules or []
    event_triggers = event_triggers or []
    workflows_by_field = {w.field.name: w for w in (workflows or [])}
    trends_by_field = {t.field.name: t for t in (trends or [])}
    trend_state: dict[str, dict] = {name: {} for name in trends_by_field}
    error_injections_by_field = {ei.field.name: ei for ei in (error_injections or [])}
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
    for position in range(count):
        previous_row = rows[-1] if rows else None
        row = None
        for _attempt in range(MAX_RULE_ATTEMPTS if rules else 1):
            candidate = _generate_one_row(
                fields,
                fk_pools,
                seen_per_field,
                unique_fk_queues,
                workflows_by_field,
                trends_by_field,
                trend_state,
                error_injections_by_field,
                previous_row,
                position,
            )
            if _row_satisfies_rules(candidate, rules):
                row = candidate
                break
        if row is None:
            raise ValueError(
                f"Could not generate a row satisfying all rules after {MAX_RULE_ATTEMPTS} "
                "attempts — the rules may be too strict or contradictory"
            )
        if event_triggers:
            row["_triggered_events"] = _evaluate_event_triggers(row, event_triggers)
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
    graph).

    Each entity's lookup attachments are merged into that same fk_pools dict
    (see build_lookup_pools) after the relationship pools are built, so a
    lookup pool wins if a field somehow ends up targeted by both — not
    cross-validated against each other, same as Trend/Workflow aren't."""
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

        fk_pools.update(build_lookup_pools(entity.lookup_attachments))

        generated[entity_id] = generate_rows(
            entity.fields,
            counts.get(entity_id, 10),
            fk_pools,
            entity.rules,
            entity.workflows,
            entity.trends,
            entity.error_injections,
            entity.event_triggers,
        )

    return generated


def rows_to_csv(fields: list[EntityField], rows: list[dict[str, Any]]) -> str:
    """Renders the declared fields as CSV columns. Workflow `<field>_history`
    values are intentionally dropped here — they're variable-length arrays,
    not a tabular column — and remain available in the JSON response."""
    fieldnames = [f.name for f in fields]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                name: json.dumps(value) if isinstance(value, (list, dict)) else value
                for name, value in row.items()
            }
        )
    return buffer.getvalue()


def _cell_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def _sheet_columns(fields: list[EntityField], rows: list[dict[str, Any]]) -> list[str]:
    declared = [f.name for f in fields]
    if not rows:
        return declared
    extra = [k for k in rows[0] if k not in declared]
    return declared + extra


def _write_sheet(ws: Worksheet, fields: list[EntityField], rows: list[dict[str, Any]]) -> None:
    columns = _sheet_columns(fields, rows)
    ws.append(columns)
    for row in rows:
        ws.append([_cell_value(row.get(col)) for col in columns])


_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _safe_sheet_name(name: str) -> str:
    return _INVALID_SHEET_CHARS.sub("_", name)[:31] or "Sheet"


def rows_to_excel(fields: list[EntityField], rows: list[dict[str, Any]]) -> bytes:
    """Unlike CSV, this includes any extra keys generation adds (e.g. a
    workflow field's `<field>_history`) alongside the declared fields —
    Excel isn't a strict fixed-column format the way CSV is."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    _write_sheet(ws, fields, rows)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def project_rows_to_excel(
    entities: list[Entity], generated: dict[uuid.UUID, list[dict[str, Any]]]
) -> bytes:
    """One workbook, one sheet per entity."""
    wb = Workbook()
    wb.remove(wb.active)
    for entity in entities:
        ws = wb.create_sheet(title=_safe_sheet_name(entity.name))
        _write_sheet(ws, entity.fields, generated.get(entity.id, []))
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def project_rows_to_csv_zip(
    entities: list[Entity], generated: dict[uuid.UUID, list[dict[str, Any]]]
) -> bytes:
    """One `<entity>.csv` file per entity, zipped together — CSV has no
    multi-table concept, so a project-wide export is a zip of flat files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for entity in entities:
            csv_text = rows_to_csv(entity.fields, generated.get(entity.id, []))
            zf.writestr(f"{entity.name}.csv", csv_text)
    return buffer.getvalue()
