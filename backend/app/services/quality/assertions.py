"""User-defined assertions that can fail a run.

`email.unique`, `orders.rows >= 100`, `status.share_paid >= 0.6` — ordinary
boolean expressions, evaluated by the same restricted evaluator that already
runs formulas, rules and event-trigger conditions
(`app.services.expressions`).

**No evaluator changes were needed**, which is the whole design. The
evaluator already resolves one level of attribute access on a dict that is
present in `variables` — the mechanism Phase 2 built so an `Order` rule
could read `Customer.age`. Assertions reuse it by putting a dict of
aggregates under each field's name. So `age.mean` and `status.share_paid`
work for exactly the same reason `Customer.age` does, and an assertion is
a thing users already know how to write rather than a third expression
dialect with its own quirks.

What that buys, beyond less code: assertions inherit the evaluator's
safety properties (no attribute access on real objects, no imports, no
arbitrary calls) without anyone having to re-establish them here, and any
rule-function plugin a deployment has installed is available in an
assertion too.

The namespace is deliberately flat and predictable:

    rows                    total rows generated
    <field>.count           non-null values
    <field>.nulls           null values
    <field>.null_share      nulls / rows
    <field>.distinct        distinct non-null values
    <field>.unique          True when every non-null value is distinct
    <field>.min/max/mean/stddev     numeric fields only (else None)
    <field>.share_<value>   share of rows holding that categorical value

`share_` is a prefix rather than bare `<field>.<value>` so a category
called "mean" cannot shadow the statistic. Category values are sanitised
into identifiers (`in progress` -> `share_in_progress`), which can in
principle collide — two categories differing only by punctuation — so the
available names are returned alongside the results for a caller to show.
"""

from __future__ import annotations

import statistics as st
from dataclasses import dataclass
from typing import Any

from app.models.field import EntityField
from app.services.expressions import ExpressionError, evaluate
from app.services.schema_import.common import sanitize_identifier

# Categories given a `share_` name. A high-cardinality column would
# otherwise add thousands of names nobody can discover or use.
MAX_SHARE_CATEGORIES = 50


@dataclass
class AssertionResult:
    expression: str
    passed: bool
    # Set when the expression could not be evaluated at all — an unknown
    # field, a typo, a comparison against the wrong type. Distinguished
    # from `passed=False` on purpose: an assertion that failed told you
    # something about the data, one that errored told you about itself.
    error: str | None = None

    @property
    def errored(self) -> bool:
        return self.error is not None


def _numeric(values: list[Any]) -> list[float]:
    return [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]


def build_context(fields: list[EntityField], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The variable namespace an assertion is evaluated against."""
    context: dict[str, Any] = {"rows": len(rows)}

    for field in fields:
        values = [row.get(field.name) for row in rows]
        present = [v for v in values if v is not None]
        numbers = _numeric(present)

        stats: dict[str, Any] = {
            "count": len(present),
            "nulls": len(values) - len(present),
            "null_share": (len(values) - len(present)) / len(values) if values else 0.0,
            "distinct": len({str(v) for v in present}),
            "unique": len(present) > 0 and len({str(v) for v in present}) == len(present),
            "min": min(numbers) if numbers else None,
            "max": max(numbers) if numbers else None,
            "mean": st.mean(numbers) if numbers else None,
            "stddev": st.stdev(numbers) if len(numbers) > 1 else None,
        }

        counts: dict[str, int] = {}
        for value in present:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
        if len(counts) <= MAX_SHARE_CATEGORIES:
            for value, count in counts.items():
                name = "share_" + sanitize_identifier(value, fallback="value")
                stats[name] = count / len(values) if values else 0.0

        context[field.name] = stats

    return context


def available_names(context: dict[str, Any]) -> list[str]:
    """Every name an assertion may reference, for showing a user what they
    can write. A silent "Unknown variable" is a bad experience when the
    namespace is generated rather than documented in advance."""
    names = []
    for key, value in context.items():
        if isinstance(value, dict):
            names.extend(f"{key}.{inner}" for inner in sorted(value))
        else:
            names.append(key)
    return sorted(names)


def check(expression: str, context: dict[str, Any]) -> AssertionResult:
    """Evaluate one assertion. Never raises — a broken assertion is a
    result, not a crash, so one typo doesn't hide the other twenty."""
    try:
        outcome = evaluate(expression, context)
    except ExpressionError as exc:
        return AssertionResult(expression, passed=False, error=str(exc))
    except Exception as exc:  # a plugin function can raise anything
        return AssertionResult(expression, passed=False, error=f"{type(exc).__name__}: {exc}")

    if not isinstance(outcome, bool):
        # `age.mean` on its own is a number, not a claim. Accepting it as
        # truthy would let "0" quietly pass as a failure and any positive
        # number as a pass, which is worse than refusing it.
        return AssertionResult(
            expression,
            passed=False,
            error=(
                f"expression produced {type(outcome).__name__} "
                f"({outcome!r}), not a true/false claim — did you mean to compare it?"
            ),
        )

    return AssertionResult(expression, passed=outcome)


def check_all(
    expressions: list[str], fields: list[EntityField], rows: list[dict[str, Any]]
) -> tuple[list[AssertionResult], dict[str, Any]]:
    """Evaluate every assertion against one shared context.

    Returns the context too, so a caller can report `available_names` when
    an assertion referenced something that doesn't exist.
    """
    context = build_context(fields, rows)
    return [check(expression, context) for expression in expressions], context
