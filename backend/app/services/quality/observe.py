"""Profile the rows that were actually generated, and check them against
what the field configuration promised.

Reuses `app.services.profiling.profile_column` — the Phase 9 profiler —
rather than writing a second one. That reuse is the point rather than a
convenience: it means "what the generated data looks like" is measured by
exactly the same code as "what the source data looked like", so a
comparison between them is meaningful instead of being an artefact of two
implementations disagreeing.

The second half is the part that finds bugs. A field declares things:
`unique`, `required`, `min_value`/`max_value`, `enum_values`. Generation is
supposed to honour them. Checking the output against the declaration turns
those promises into assertions about the engine, and a violation here is a
real defect rather than a matter of taste — which is why violations are
separated from observations in the result.
"""

from __future__ import annotations

import statistics as st
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from app.models.field import EntityField, FieldType
from app.services.profiling.profile import MIN_CORRELATION, ColumnProfile, profile_column

# Correlations are only reported between columns with at least this many
# usable numeric values — below it the coefficient is noise.
MIN_ROWS_FOR_CORRELATION = 20

# Categories listed in the observed summary.
MAX_REPORTED_CATEGORIES = 10


@dataclass
class ColumnObservation:
    name: str
    declared_type: str
    observed_type: str
    rows: int
    nulls: int
    null_share: float
    distinct: int
    is_unique: bool
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    stddev: float | None = None
    fitted: str | None = None
    fit_quality: str | None = None
    categories: dict[str, float] = dataclass_field(default_factory=dict)


@dataclass
class Violation:
    """A generated value contradicting the field's own declaration. Not a
    style opinion — the engine promised something and did not deliver it."""

    field: str
    kind: str
    detail: str


@dataclass
class Observation:
    rows: int
    columns: list[ColumnObservation]
    violations: list[Violation]
    correlations: list[dict[str, Any]]

    def as_dict(self) -> dict:
        return {
            "rows": self.rows,
            "columns": [
                {
                    "name": c.name,
                    "declared_type": c.declared_type,
                    "observed_type": c.observed_type,
                    "rows": c.rows,
                    "nulls": c.nulls,
                    "null_share": round(c.null_share, 4),
                    "distinct": c.distinct,
                    "is_unique": c.is_unique,
                    "min": c.min,
                    "max": c.max,
                    "mean": c.mean,
                    "stddev": c.stddev,
                    "fitted": c.fitted,
                    "fit_quality": c.fit_quality,
                    "categories": c.categories,
                }
                for c in self.columns
            ],
            "violations": [
                {"field": v.field, "kind": v.kind, "detail": v.detail} for v in self.violations
            ],
            "correlations": self.correlations,
        }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _check_declaration(
    field: EntityField, profile: ColumnProfile, values: list[Any]
) -> list[Violation]:
    present = [v for v in values if v is not None]
    violations: list[Violation] = []

    if field.required and profile.missing:
        violations.append(
            Violation(
                field.name,
                "required_but_null",
                f"declared required, but {profile.missing} of {profile.total} rows are null",
            )
        )

    if field.unique and present and profile.distinct < len(present):
        duplicates = len(present) - profile.distinct
        violations.append(
            Violation(
                field.name,
                "unique_but_duplicated",
                f"declared unique, but {duplicates} duplicate value(s) were generated",
            )
        )

    if field.enum_values:
        allowed = {str(v) for v in field.enum_values}
        unexpected = {str(v) for v in present} - allowed
        if unexpected:
            # Named without quoting more than a couple, since an enum can be
            # long and the point is that *something* escaped the set.
            sample = ", ".join(sorted(unexpected)[:3])
            violations.append(
                Violation(
                    field.name,
                    "value_outside_enum",
                    f"{len(unexpected)} value(s) not in enum_values: {sample}",
                )
            )

    numeric = [float(v) for v in present if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if numeric:
        if field.min_value is not None and min(numeric) < field.min_value:
            violations.append(
                Violation(
                    field.name,
                    "below_min",
                    f"declared min_value {field.min_value}, but {min(numeric)} was generated",
                )
            )
        if field.max_value is not None and max(numeric) > field.max_value:
            violations.append(
                Violation(
                    field.name,
                    "above_max",
                    f"declared max_value {field.max_value}, but {max(numeric)} was generated",
                )
            )

    return violations


def _correlations(observations: dict[str, list[float]]) -> list[dict[str, Any]]:
    """Pairwise correlation between numeric columns.

    Reported as a list of pairs above a threshold rather than a full N x N
    matrix: the matrix is mostly zeroes, and what a reader wants is "these
    two move together", not 400 cells to scan.
    """
    names = [n for n, v in observations.items() if len(v) >= MIN_ROWS_FOR_CORRELATION]
    found: list[dict[str, Any]] = []
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            left, right = observations[first], observations[second]
            size = min(len(left), len(right))
            if size < MIN_ROWS_FOR_CORRELATION:
                continue
            if len(set(left[:size])) < 2 or len(set(right[:size])) < 2:
                continue
            try:
                coefficient = st.correlation(left[:size], right[:size])
            except st.StatisticsError:
                continue
            if abs(coefficient) >= MIN_CORRELATION:
                found.append({"between": [first, second], "correlation": round(coefficient, 4)})
    return found


def observe_rows(fields: list[EntityField], rows: list[dict[str, Any]]) -> Observation:
    """Profile generated rows and check them against their declarations."""
    by_name = {f.name: f for f in fields}
    columns: list[ColumnObservation] = []
    violations: list[Violation] = []
    numeric_by_column: dict[str, list[float]] = {}
    taken: set[str] = set()

    for name, field in by_name.items():
        values = [row.get(name) for row in rows]
        profile = profile_column(name, values, taken)

        present = [v for v in values if v is not None]
        numeric = [
            float(v) for v in present if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if len(numeric) >= MIN_ROWS_FOR_CORRELATION:
            numeric_by_column[name] = numeric

        categories: dict[str, float] = {}
        if profile.categories and profile.weights:
            categories = dict(
                zip(
                    profile.categories[:MAX_REPORTED_CATEGORIES],
                    (round(w, 4) for w in profile.weights[:MAX_REPORTED_CATEGORIES]),
                    strict=False,
                )
            )

        columns.append(
            ColumnObservation(
                name=name,
                declared_type=(
                    field.field_type.value
                    if isinstance(field.field_type, FieldType)
                    else str(field.field_type)
                ),
                observed_type=profile.inferred_type,
                rows=profile.total,
                nulls=profile.missing,
                null_share=profile.null_rate,
                distinct=profile.distinct,
                is_unique=profile.unique,
                min=_round(min(numeric)) if numeric else None,
                max=_round(max(numeric)) if numeric else None,
                mean=_round(st.mean(numeric)) if numeric else None,
                stddev=_round(st.stdev(numeric)) if len(numeric) > 1 else None,
                fitted=profile.fit.expression if profile.fit else None,
                fit_quality=profile.fit.quality if profile.fit else None,
                categories=categories,
            )
        )
        violations.extend(_check_declaration(field, profile, values))

    return Observation(
        rows=len(rows),
        columns=columns,
        violations=violations,
        correlations=_correlations(numeric_by_column),
    )
