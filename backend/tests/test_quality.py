"""Phase 11 — generation diagnostics, output observation, and assertions."""

import random
from types import SimpleNamespace

import pytest

from app.models.field import FieldType
from app.services.generator import MAX_UNIQUE_ATTEMPTS, iter_rows
from app.services.quality.assertions import available_names, build_context, check, check_all
from app.services.quality.diagnostics import GenerationDiagnostics
from app.services.quality.observe import observe_rows


def field(**overrides):
    """A bare EntityField-shaped stand-in. The generator only reads
    attributes, so this avoids a database round-trip per test."""
    base = dict(
        name="value",
        field_type=FieldType.STRING,
        formula=None,
        preset=None,
        regex=None,
        min_value=None,
        max_value=None,
        enum_values=None,
        enum_weights=None,
        required=True,
        nullable=False,
        unique=False,
        default_value=None,
        order=0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def rule(condition: str):
    return SimpleNamespace(condition=condition, name=condition)


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------


def test_no_diagnostics_means_no_bookkeeping():
    """Collection is opt-in so the streaming path stays exactly as cheap."""
    rows = list(iter_rows([field(name="a", field_type=FieldType.INTEGER)], 10))
    assert len(rows) == 10


def test_discarded_candidates_are_counted_and_attributed():
    random.seed(1)
    diagnostics = GenerationDiagnostics()
    amount = field(name="amount", field_type=FieldType.INTEGER, min_value=1, max_value=100)
    rows = list(iter_rows([amount], 50, rules=[rule("amount > 90")], diagnostics=diagnostics))

    assert len(rows) == 50
    assert diagnostics.rows_yielded == 50
    # Most candidates fail a rule that only accepts the top 10% of the range.
    assert diagnostics.candidates_generated > 50
    assert diagnostics.candidates_discarded > 0
    assert diagnostics.discards_by_rule["amount > 90"] == diagnostics.candidates_discarded


def test_discard_counts_sum_to_the_total_rather_than_double_counting():
    """Attribution stops at the first failing rule, which is also what the
    engine checks — so two rules cannot both claim the same candidate."""
    random.seed(2)
    diagnostics = GenerationDiagnostics()
    amount = field(name="amount", field_type=FieldType.INTEGER, min_value=1, max_value=100)
    list(
        iter_rows(
            [amount],
            30,
            rules=[rule("amount > 50"), rule("amount < 90")],
            diagnostics=diagnostics,
        )
    )
    assert sum(diagnostics.discards_by_rule.values()) == diagnostics.candidates_discarded


def test_a_high_discard_rate_is_reported_as_a_finding():
    random.seed(3)
    diagnostics = GenerationDiagnostics()
    amount = field(name="amount", field_type=FieldType.INTEGER, min_value=1, max_value=100)
    list(iter_rows([amount], 40, rules=[rule("amount > 95")], diagnostics=diagnostics))

    findings = diagnostics.findings(MAX_UNIQUE_ATTEMPTS)
    assert any("discarded by rules" in f for f in findings)
    assert any("amount > 95" in f for f in findings)


def test_error_injection_cancelled_by_a_rule_is_surfaced():
    """The interaction the generator has documented since it was written:
    corruption runs *before* rule checking, so a rule on the same field
    silently undoes it. You ask for 50% bad values and get 0%, with no
    error and — until now — no warning."""
    random.seed(4)
    email = field(name="email", field_type=FieldType.STRING, regex=r"[a-z]{5}@t\.com")
    injection = SimpleNamespace(field=email, rate=0.5, error_types=["null"])
    diagnostics = GenerationDiagnostics()

    list(
        iter_rows(
            [email],
            100,
            rules=[rule("email != None")],
            error_injections=[injection],
            diagnostics=diagnostics,
        )
    )

    assert diagnostics.injections_applied["email"] > 0
    assert diagnostics.injections_surviving.get("email", 0) == 0
    assert diagnostics.survival_share("email") == 0.0
    assert any("error injection on 'email'" in f for f in diagnostics.findings(MAX_UNIQUE_ATTEMPTS))


def test_injection_that_survives_is_not_reported():
    """No rule, so nothing undoes the corruption — and a report that always
    has content trains people to ignore it."""
    random.seed(5)
    note = field(name="note", field_type=FieldType.STRING, nullable=True, required=False)
    injection = SimpleNamespace(field=note, rate=0.9, error_types=["null"])
    diagnostics = GenerationDiagnostics()

    list(iter_rows([note], 100, error_injections=[injection], diagnostics=diagnostics))

    assert diagnostics.survival_share("note") == 1.0
    assert not any("error injection" in f for f in diagnostics.findings(MAX_UNIQUE_ATTEMPTS))


def test_unique_retries_are_counted():
    """Rising retries are the only warning available before a unique pool
    fails outright."""
    random.seed(6)
    diagnostics = GenerationDiagnostics()
    # A tiny value space forces collisions well before the cap.
    small = field(name="code", field_type=FieldType.INTEGER, min_value=1, max_value=60, unique=True)
    list(iter_rows([small], 50, diagnostics=diagnostics))
    assert diagnostics.unique_retries["code"] > 0


def test_a_clean_run_reports_nothing():
    random.seed(7)
    diagnostics = GenerationDiagnostics()
    list(iter_rows([field(name="a", field_type=FieldType.INTEGER)], 25, diagnostics=diagnostics))
    assert diagnostics.findings(MAX_UNIQUE_ATTEMPTS) == []
    assert diagnostics.discard_share == 0.0


# --------------------------------------------------------------------------
# Observation
# --------------------------------------------------------------------------


def _basic_fields():
    return [
        field(name="age", field_type=FieldType.INTEGER, min_value=18, max_value=90),
        field(name="score", field_type=FieldType.FLOAT, formula="2.5*age + 30 + noise(5)"),
        field(
            name="tier",
            field_type=FieldType.ENUM,
            enum_values=["free", "pro", "ent"],
            enum_weights=[0.6, 0.3, 0.1],
        ),
    ]


def test_observation_measures_what_was_generated():
    random.seed(8)
    fields = _basic_fields()
    rows = list(iter_rows(fields, 200))
    observation = observe_rows(fields, rows)

    by_name = {c.name: c for c in observation.columns}
    assert observation.rows == 200
    assert by_name["age"].min >= 18
    assert by_name["age"].max <= 90
    assert by_name["tier"].distinct == 3
    assert set(by_name["tier"].categories) == {"free", "pro", "ent"}


def test_a_correlation_the_formula_created_is_detected():
    """Reuses the Phase 9 profiler, so "what the generated data looks like"
    is measured by the same code as "what the source looked like"."""
    random.seed(9)
    fields = _basic_fields()
    rows = list(iter_rows(fields, 200))
    observation = observe_rows(fields, rows)

    pairs = {tuple(sorted(c["between"])) for c in observation.correlations}
    assert ("age", "score") in pairs


def test_a_clean_run_has_no_violations():
    random.seed(10)
    fields = _basic_fields()
    observation = observe_rows(fields, list(iter_rows(fields, 100)))
    assert observation.violations == []


def test_output_contradicting_its_declaration_is_a_violation():
    """Violations are checked against the field's own promises, so this
    doesn't depend on the generator being wrong — feeding it rows that
    break the contract must be caught."""
    fields = [
        field(name="code", field_type=FieldType.INTEGER, min_value=10, max_value=20, unique=True),
        field(name="tier", field_type=FieldType.ENUM, enum_values=["a", "b"], required=True),
    ]
    rows = [
        {"code": 5, "tier": "a"},  # below min
        {"code": 5, "tier": "z"},  # duplicate, and outside the enum
        {"code": 99, "tier": None},  # above max, and null in a required field
    ]
    kinds = {v.kind for v in observe_rows(fields, rows).violations}
    assert kinds == {
        "below_min",
        "above_max",
        "unique_but_duplicated",
        "value_outside_enum",
        "required_but_null",
    }


# --------------------------------------------------------------------------
# Assertions
# --------------------------------------------------------------------------


def _assertion_fields():
    return [
        field(name="email", field_type=FieldType.STRING, regex=r"[a-z]{8}@t\.com", unique=True),
        field(name="age", field_type=FieldType.INTEGER, min_value=18, max_value=90),
        field(
            name="status",
            field_type=FieldType.ENUM,
            enum_values=["paid", "pending", "failed"],
            enum_weights=[0.7, 0.2, 0.1],
        ),
    ]


@pytest.mark.parametrize(
    "expression",
    [
        "email.unique",
        "rows == 300",
        "age.min >= 18",
        "age.max <= 90",
        "email.nulls == 0",
        "status.share_paid > 0.5",
        "status.distinct == 3",
    ],
)
def test_assertions_that_should_hold(expression):
    random.seed(11)
    fields = _assertion_fields()
    rows = list(iter_rows(fields, 300))
    results, _ = check_all([expression], fields, rows)
    assert results[0].passed, results[0].error


def test_a_failing_assertion_is_a_result_not_an_error():
    random.seed(12)
    fields = _assertion_fields()
    rows = list(iter_rows(fields, 300))
    results, _ = check_all(["status.share_failed > 0.9"], fields, rows)
    assert results[0].passed is False
    assert results[0].errored is False


def test_a_broken_assertion_does_not_hide_the_others():
    """One typo must not take the whole report down with it."""
    random.seed(13)
    fields = _assertion_fields()
    rows = list(iter_rows(fields, 100))
    results, _ = check_all(["nonexistent.mean > 1", "rows == 100"], fields, rows)
    assert results[0].errored is True
    assert results[1].passed is True


def test_a_non_boolean_expression_is_rejected_rather_than_coerced():
    """`age.mean` is a number, not a claim. Treating it as truthy would let
    0 read as a failure and any positive number as a pass."""
    random.seed(14)
    fields = _assertion_fields()
    rows = list(iter_rows(fields, 50))
    results, _ = check_all(["age.mean"], fields, rows)
    assert results[0].passed is False
    assert results[0].errored is True
    assert "not a true/false claim" in results[0].error


def test_the_available_namespace_is_discoverable():
    """The namespace is generated, not documented in advance, so a caller
    has to be able to show what can be referenced."""
    random.seed(15)
    fields = _assertion_fields()
    context = build_context(fields, list(iter_rows(fields, 50)))
    names = available_names(context)
    assert "rows" in names
    assert "age.mean" in names
    assert "status.share_paid" in names


def test_share_names_are_prefixed_so_a_category_cannot_shadow_a_statistic():
    """A category literally called "mean" must not overwrite `.mean`."""
    fields = [field(name="label", field_type=FieldType.ENUM, enum_values=["mean", "other"])]
    rows = [{"label": "mean"}, {"label": "other"}]
    context = build_context(fields, rows)
    assert context["label"]["share_mean"] == 0.5
    # `.mean` stays the statistic (None, since the column isn't numeric).
    assert context["label"]["mean"] is None


def test_assertions_reuse_the_expression_evaluator_safely():
    """Assertions inherit the evaluator's restrictions rather than
    re-establishing them — no imports, no attribute access on real
    objects."""
    context = build_context([field(name="a", field_type=FieldType.INTEGER)], [{"a": 1}])
    for hostile in ("__import__('os').system('true')", "a.__class__", "open('/etc/passwd')"):
        assert check(hostile, context).errored is True
