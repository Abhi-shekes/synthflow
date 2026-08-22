"""Learn a project from real sample data.

Phase 7's sample import is deliberately shallow — types, observed ranges,
enums. This is the deep version: it fits an actual distribution per
numeric column, measures categorical frequencies, and detects
correlations between columns, so generated data has the *shape* of the
original rather than merely its schema.

The design decision that shapes everything here: **nothing new is
persisted.** A profile becomes an ordinary `ProjectTemplate` whose fields
carry formulas like `round(gauss(41.2, 12.1))` and enum weights like
`[0.62, 0.31, 0.07]`. There is no learned-model table, no opaque blob —
the inferred distribution is a formula the user can read, edit, diff and
version-control like anything else, and it runs on the generation engine
that already exists.

That was possible because three of this phase's four hard parts turned
out to already have homes:

- categorical frequencies → `enum_values` + `enum_weights` (Phase 4)
- correlation → a formula referencing another field plus `noise()`
  (Phase 4's correlation work said exactly this)
- continuous distributions → the one genuine gap, closed by adding
  `gauss`/`lognormal`/`expo`/`triangular` to the expression evaluator
  rather than adding a `distribution` column and an engine to read it

Missing values are reproduced too: a column that was 3% empty generates
3% nulls, and one that was 40% empty generates 40%. That used to be the
one measured thing this could not reproduce — every nullable field got a
flat 15% — and it is now carried on the field itself as
`EntityField.null_probability`.
"""

import statistics as st
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from typing import Any

from app.schemas.template import TemplateEntity, TemplateField, TemplateRelationship
from app.services.lookup_tables import parse_upload
from app.services.privacy.bounds import round_bounds
from app.services.privacy.classify import PiiFinding, PiiKind, classify_column
from app.services.profiling.distributions import MIN_SAMPLES_FOR_FIT, Fit, fit_best
from app.services.schema_import.common import (
    ImportResult,
    dedupe,
    empty_template,
    make_field,
    sanitize_identifier,
)

# A column emptier than this generates a column that is almost entirely
# empty, which is faithful and usually not what anyone wanted — so it is
# still worth a word, even though the rate itself is now reproduced.
NEARLY_ALL_NULL = 0.9

# A *text* column with at most this many distinct values is categorical.
MAX_CATEGORICAL_VALUES = 25
# Numbers get a far tighter bar. A 1-5 rating or a status code is
# genuinely categorical; a quantity with 13 distinct values is not, and
# treating it as one both loses its shape and — because correlation
# detection only considers fitted numeric columns — silently destroys any
# relationship it had with another column. Found by profiling real
# multi-file data, where `total`'s dependency on `qty` vanished.
MAX_NUMERIC_CATEGORICAL_VALUES = 10
# Two numeric columns this correlated get expressed as a formula.
MIN_CORRELATION = 0.6
# A foreign-key candidate must have at least this share of its values
# present in the referenced column.
MIN_FK_COVERAGE = 0.95
# ...but coverage alone is a trap: *any* small-range integer column is
# "contained" in a large id column, which linked `orders.qty` to
# `customers.cid` and `customers.age` to `orders.oid` the first time this
# ran on real data. So a candidate must ALSO either share a name with the
# target column or reference a substantial share of its distinct keys.
MIN_FK_DISTINCT_RATIO = 0.5
# Below this many distinct values a column is a flag or a small code, not
# a foreign key, whatever its values happen to coincide with.
MIN_FK_DISTINCT = 8


class ProfileError(ValueError):
    pass


@dataclass
class ColumnProfile:
    name: str
    field_name: str
    inferred_type: str
    total: int
    missing: int
    distinct: int
    numeric_values: list[float] = dataclass_field(default_factory=list)
    text_values: list[str] = dataclass_field(default_factory=list)
    fit: Fit | None = None
    categories: list[str] | None = None
    weights: list[float] | None = None
    unique: bool = False
    # What kind of personal data this column appears to hold, if any — see
    # app.services.privacy.classify. Set during profiling and consumed by
    # `_to_field`, which is what makes redaction structural: a HIGH-
    # confidence finding returns a preset-backed field before any branch
    # that could emit an observed value.
    pii: PiiFinding | None = None

    @property
    def null_rate(self) -> float:
        return self.missing / self.total if self.total else 0.0

    @property
    def redacted(self) -> bool:
        return self.pii is not None and self.pii.should_redact


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _classify(values: list[Any]) -> str:
    present = [v for v in values if v is not None and v != ""]
    if not present:
        return "string"
    if all(isinstance(v, bool) for v in present):
        return "boolean"
    if all(_is_number(v) and float(v).is_integer() for v in present):
        return "integer"
    if all(_is_number(v) for v in present):
        return "float"
    if all(isinstance(v, (date, datetime)) for v in present):
        return "datetime" if any(isinstance(v, datetime) for v in present) else "date"
    return "string"


def profile_column(name: str, values: list[Any], taken: set[str]) -> ColumnProfile:
    present = [v for v in values if v is not None and v != ""]
    inferred = _classify(values)
    field_name = dedupe(sanitize_identifier(name, fallback="column"), taken)

    profile = ColumnProfile(
        name=name,
        field_name=field_name,
        inferred_type=inferred,
        total=len(values),
        missing=len(values) - len(present),
        distinct=len({str(v) for v in present}),
    )
    profile.unique = len(present) > 1 and profile.distinct == len(present)

    # Classify before any of the branches below, so that what gets learned
    # from a personal-data column is decided in one place rather than
    # depending on which branch the column happened to fall into.
    profile.pii = classify_column(
        name, [str(v) for v in present], numeric=inferred in ("integer", "float")
    )

    if inferred in ("integer", "float"):
        profile.numeric_values = [float(v) for v in present]
        # A numeric column with few distinct values (a rating, a status
        # code) is really categorical — fitting a bell curve to it would
        # be worse than counting its frequencies.
        if (
            profile.distinct <= MAX_NUMERIC_CATEGORICAL_VALUES
            and profile.distinct < len(present) / 4
        ):
            profile.categories, profile.weights = _frequencies([str(v) for v in present])
        else:
            profile.fit = fit_best(profile.numeric_values)
    else:
        profile.text_values = [str(v) for v in present]
        if 1 < profile.distinct <= MAX_CATEGORICAL_VALUES and not profile.unique:
            profile.categories, profile.weights = _frequencies(profile.text_values)

    return profile


def _frequencies(values: list[str]) -> tuple[list[str], list[float]]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    total = len(values)
    return (
        [name for name, _ in ordered],
        [round(count / total, 4) for _, count in ordered],
    )


def _correlations(profiles: list[ColumnProfile]) -> dict[str, tuple[str, float, float, float]]:
    """Find, per column, the earlier column it correlates with most.

    Returns dependent -> (driver, slope, intercept, residual stddev).
    Only ever points *backwards* through the column order, which
    guarantees no cycles and satisfies the formula engine's rule that a
    formula may only reference earlier-ordered fields.
    """
    # Redacted columns are excluded as both driver and dependent. A numeric
    # column holding personal data (an SSN or phone stored as a number)
    # becomes a preset-backed *string* field, so a formula referencing it
    # would be both broken and a way to reconstruct information about the
    # value that was redacted.
    numeric = [
        p
        for p in profiles
        if p.fit is not None and not p.redacted and len(p.numeric_values) >= MIN_SAMPLES_FOR_FIT
    ]
    found: dict[str, tuple[str, float, float, float]] = {}

    for index, dependent in enumerate(numeric):
        best: tuple[str, float, float, float] | None = None
        best_r = MIN_CORRELATION
        for driver in numeric[:index]:
            if len(driver.numeric_values) != len(dependent.numeric_values):
                # Different row counts mean missing values knocked them
                # out of alignment; comparing them would be meaningless.
                continue
            try:
                r = st.correlation(driver.numeric_values, dependent.numeric_values)
            except st.StatisticsError:
                continue
            if abs(r) > abs(best_r):
                regression = st.linear_regression(driver.numeric_values, dependent.numeric_values)
                predicted = [
                    regression.intercept + regression.slope * x for x in driver.numeric_values
                ]
                residuals = [
                    actual - fitted
                    for actual, fitted in zip(dependent.numeric_values, predicted, strict=True)
                ]
                residual_sd = st.stdev(residuals) if len(residuals) > 1 else 0.0
                best_r = r
                best = (
                    driver.field_name,
                    round(regression.slope, 4),
                    round(regression.intercept, 4),
                    round(residual_sd, 4),
                )
        if best is not None:
            found[dependent.field_name] = best
    return found


# What to generate instead of each kind of personal data. Mostly the
# PiiPreset of the same name (app.services.pii_generators); PAN maps to the
# pre-existing IdentifierPreset rather than duplicating that generator.
_PII_PRESETS: dict[PiiKind, str] = {
    PiiKind.PERSON_NAME: "person_name",
    PiiKind.EMAIL_ADDRESS: "email_address",
    PiiKind.PHONE_NUMBER: "phone_number",
    PiiKind.STREET_ADDRESS: "street_address",
    PiiKind.POSTCODE: "postcode",
    PiiKind.PAYMENT_CARD: "payment_card",
    PiiKind.SSN: "ssn",
    PiiKind.AADHAAR: "aadhaar",
    PiiKind.PAN: "pan",
    PiiKind.IP_ADDRESS: "ip_address",
    PiiKind.USERNAME: "username",
    PiiKind.DATE_OF_BIRTH: "date_of_birth",
}


def _to_field(
    profile: ColumnProfile, order: int, correlation, result: ImportResult
) -> TemplateField:
    required = profile.missing == 0
    common = {
        "order": order,
        "required": required,
        "nullable": not required,
        "unique": profile.unique,
        # The observed rate, carried straight through. Every branch below
        # spreads `common`, so this reaches enum, numeric, redacted and
        # plain-string fields alike rather than needing five edits — which
        # is also why a branch added later gets it for free.
        #
        # `None` for a required field: a field that is never null has no
        # null rate to express, and 0.0 would read as an explicit choice
        # somebody made rather than the absence of one.
        "null_probability": None if required else profile.null_rate,
    }

    # Personal data is handled before anything else on purpose. Every
    # branch below this point puts observed values into the template —
    # enum_values are the real categories, min/max are two real records'
    # values — so redaction has to happen here rather than as a cleanup
    # pass afterwards, where a later-added branch could quietly bypass it.
    if profile.redacted:
        assert profile.pii is not None
        preset = _PII_PRESETS.get(profile.pii.kind)
        result.warn(
            f"{profile.name}: looks like {profile.pii.kind.value} "
            f"({profile.pii.reason}) — replaced with synthetic values, so no "
            f"value from the sample file was copied into this project"
        )
        if preset is not None:
            field = make_field(profile.field_name, "string", **common)
            field.preset = preset
            return field
        # Classified, but with no synthetic equivalent to swap in. Emit a
        # plain string field rather than the observed values: losing the
        # column's shape is the right trade against copying real data.
        return make_field(profile.field_name, "string", **common)

    if profile.categories:
        return make_field(
            profile.field_name,
            "enum",
            enum_values=profile.categories,
            **common,
        )

    if profile.inferred_type in ("integer", "float"):
        rounding = "round(%s)" if profile.inferred_type == "integer" else "%s"

        if correlation is not None:
            driver, slope, intercept, residual = correlation
            body = f"{intercept} + {slope} * {driver}"
            if residual > 0:
                body += f" + noise({residual})"
            result.warn(
                f"{profile.name}: correlated with '{driver}' — expressed as a formula so "
                f"the relationship survives generation, not just the marginal shape"
            )
            return _formula_field(
                profile.field_name, profile.inferred_type, rounding % f"({body})", common
            )

        if profile.fit is not None:
            return _formula_field(
                profile.field_name,
                profile.inferred_type,
                rounding % profile.fit.expression,
                common,
            )

        # Not enough data to justify a shape — fall back to the observed
        # range, which is what Phase 7's shallow import would have done.
        # Rounded outward for the same reason `_try_uniform` rounds: this is
        # the small-sample path, where min and max are *more* attributable
        # to an individual, not less.
        values = profile.numeric_values
        low, high = round_bounds(min(values), max(values)) if values else (None, None)
        return make_field(
            profile.field_name,
            profile.inferred_type,
            min_value=low,
            max_value=high,
            **common,
        )

    return make_field(profile.field_name, profile.inferred_type, **common)


def _formula_field(name: str, field_type: str, formula: str, common: dict) -> TemplateField:
    field = make_field(name, field_type, **common)
    field.formula = formula
    # A computed field can't also be drawn from a unique pool.
    field.unique = False
    return field


def profile_file(
    filename: str,
    content: bytes,
    *,
    max_rows: int,
    entity_name: str | None = None,
) -> tuple[TemplateEntity, list[ColumnProfile], list[str]]:
    """Profile an uploaded file: parse it, then profile the table."""
    try:
        columns, rows = parse_upload(filename, content, max_rows)
    except ValueError as exc:
        raise ProfileError(str(exc)) from exc
    if not columns:
        raise ProfileError(f"No columns found in '{filename}'.")

    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0] or "Record"
    return profile_table(entity_name or stem, columns, rows)


def profile_table(
    source_name: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> tuple[TemplateEntity, list[ColumnProfile], list[str]]:
    """Profile rows that are already parsed.

    Split out from `profile_file` so a source that produces real rows —
    a database table (Phase 12) — can skip the file round-trip entirely.
    That is not just tidiness: serialising a table to CSV and parsing it
    back turns DATE and DATETIME columns into strings, so a database would
    have profiled *worse* than the same data exported by hand. Going
    straight from rows keeps the driver's native types.
    """
    if not columns:
        raise ProfileError(f"No columns found in '{source_name}'.")

    warnings: list[str] = []
    name = sanitize_identifier(source_name, fallback="Record")

    taken: set[str] = set()
    profiles = [profile_column(c, [r.get(c) for r in rows], taken) for c in columns]

    scratch = ImportResult(template=empty_template("scratch"))
    correlations = _correlations(profiles)
    fields = [
        _to_field(p, i, correlations.get(p.field_name), scratch) for i, p in enumerate(profiles)
    ]
    warnings.extend(scratch.warnings)

    for p in profiles:
        if p.field_name != p.name:
            warnings.append(f"Column '{p.name}': renamed to '{p.field_name}'")
        if p.fit is not None and p.fit.quality == "rough":
            warnings.append(
                f"{p.name}: no candidate distribution matched well (best was "
                f"{p.fit.kind}); the generated shape will only be indicative"
            )
        if p.null_rate >= NEARLY_ALL_NULL:
            # No longer a limitation, but still worth saying: a column this
            # empty was probably not meant to carry data, and reproducing
            # 98% nulls faithfully is rarely what someone wants.
            warnings.append(
                f"{p.name}: {p.null_rate:.0%} of values were missing, so the generated "
                f"column will be almost entirely empty too — check that this column is "
                f"worth keeping"
            )
    if len(rows) < MIN_SAMPLES_FOR_FIT:
        warnings.append(
            f"Only {len(rows)} rows were sampled — too few to fit distributions, so "
            f"numeric columns fell back to their observed ranges."
        )

    return TemplateEntity(name=name, fields=fields), profiles, warnings


def _names_related(source_field: str, target_entity: str, target_field: str) -> bool:
    """Whether the column names suggest a reference, e.g. `cid` -> `cid`,
    `customer_id` -> `customers.id`, `user_ref` -> `users.ref`."""
    a, b = source_field.lower(), target_field.lower()
    if a == b:
        return True
    entity = target_entity.lower().rstrip("s")
    return a.startswith(entity) and (a.endswith(b) or b in a)


def _detect_foreign_keys(
    entities: list[TemplateEntity],
    profiles_by_entity: dict[str, list[ColumnProfile]],
    result: ImportResult,
) -> None:
    """Link entities when one column's values are a subset of another's
    unique column *and* the pairing is otherwise plausible.

    Value coverage is the necessary condition but nowhere near
    sufficient — see MIN_FK_DISTINCT_RATIO. Links that would create a
    cycle between two entities are also rejected, because
    `generate_project` orders entities by dependency and a cycle has no
    valid order.
    """
    unique_columns: list[tuple[str, str, set[str]]] = []
    for entity in entities:
        for profile in profiles_by_entity[entity.name]:
            # A redacted column is never an FK target: its generated values
            # come from a preset and have no relationship to the values a
            # child column was matched against, so the link would not hold
            # in the generated data even though it held in the sample.
            if profile.unique and profile.distinct > 1 and not profile.redacted:
                values = {str(v) for v in (profile.numeric_values or profile.text_values)}
                unique_columns.append((entity.name, profile.field_name, values))

    # source entity -> target entities it already points at, so a
    # reciprocal link can be refused.
    edges: dict[str, set[str]] = {}

    for entity in entities:
        for profile in profiles_by_entity[entity.name]:
            if profile.unique or profile.redacted or profile.distinct < MIN_FK_DISTINCT:
                continue
            candidate = {str(v) for v in (profile.numeric_values or profile.text_values)}
            if not candidate:
                continue

            for target_entity, target_field, target_values in unique_columns:
                if target_entity == entity.name or not target_values:
                    continue
                if target_entity in edges.get(entity.name, set()):
                    continue
                # Would completing this link close a cycle?
                if entity.name in edges.get(target_entity, set()):
                    result.warn(
                        f"{entity.name}.{profile.field_name}: not linked to "
                        f"{target_entity}.{target_field} — it would make the two "
                        f"entities reference each other, which has no generation order"
                    )
                    continue

                covered = len(candidate & target_values) / len(candidate)
                if covered < MIN_FK_COVERAGE:
                    continue

                distinct_ratio = len(candidate) / len(target_values)
                if not (
                    _names_related(profile.field_name, target_entity, target_field)
                    or distinct_ratio >= MIN_FK_DISTINCT_RATIO
                ):
                    # Contained, but almost certainly a coincidence.
                    continue

                result.template.relationships.append(
                    TemplateRelationship(
                        relationship_type="one_to_many",
                        source_entity=entity.name,
                        source_field=profile.field_name,
                        target_entity=target_entity,
                        target_field=target_field,
                    )
                )
                edges.setdefault(entity.name, set()).add(target_entity)
                result.warn(
                    f"{entity.name}.{profile.field_name}: {covered:.0%} of its values "
                    f"appear in {target_entity}.{target_field}, so it was linked as a "
                    f"relationship — remove it if that's a coincidence"
                )
                break


def profile_files(
    files: list[tuple[str, bytes]],
    *,
    max_rows: int,
    project_name: str | None = None,
) -> tuple[ImportResult, dict[str, list[ColumnProfile]]]:
    """Profile one or more related files into a single project.

    Returns the template alongside the per-column profiles, so a caller
    can show *why* a field looks the way it does — the observed row
    count, null count and cardinality behind each fitted formula — rather
    than only the formula itself.
    """
    if not files:
        raise ProfileError("No files given.")

    parsed: list[tuple[str, list[str], list[dict[str, Any]]]] = []
    for filename, content in files:
        try:
            columns, rows = parse_upload(filename, content, max_rows)
        except ValueError as exc:
            raise ProfileError(str(exc)) from exc
        stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0] or "Record"
        parsed.append((stem, columns, rows))

    return profile_tables(parsed, project_name=project_name, source_label="sample file")


def profile_tables(
    tables: list[tuple[str, list[str], list[dict[str, Any]]]],
    *,
    project_name: str | None = None,
    source_label: str = "table",
) -> tuple[ImportResult, dict[str, list[ColumnProfile]]]:
    """Profile already-parsed tables into a single project.

    The half of `profile_files` that has nothing to do with files, so a
    database (Phase 12's input connectors) reaches relationship detection
    and correlation analysis through exactly the same code — including
    across several tables at once, which is what makes foreign keys
    detectable.
    """
    if not tables:
        raise ProfileError("Nothing to profile.")

    result = ImportResult(
        template=empty_template(
            project_name or "Learned from data",
            description=(
                f"Learned from {len(tables)} {source_label}"
                f"{'s' if len(tables) != 1 else ''}: distributions and "
                f"correlations fitted from the observed values."
            ),
        )
    )

    profiles_by_entity: dict[str, list[ColumnProfile]] = {}
    for source_name, columns, rows in tables:
        entity, profiles, warnings = profile_table(source_name, columns, rows)
        result.template.entities.append(entity)
        profiles_by_entity[entity.name] = profiles
        for warning in warnings:
            result.warn(warning)

    # Weights live on the template's fields; apply them after the fields
    # exist so enum_values and enum_weights stay aligned.
    for entity in result.template.entities:
        by_name = {p.field_name: p for p in profiles_by_entity[entity.name]}
        for field in entity.fields:
            profile = by_name.get(field.name)
            if profile is not None and profile.weights and field.enum_values:
                field.enum_weights = profile.weights

    if len(result.template.entities) > 1:
        _detect_foreign_keys(result.template.entities, profiles_by_entity, result)

    return result, profiles_by_entity
