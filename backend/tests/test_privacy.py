"""Phase 10 — PII classification, redaction during profiling, and secret
encryption at rest."""

import csv
import io
import random

import pytest

from app.core import secrets
from app.core.secrets import (
    PREFIX,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)
from app.services.privacy.anonymity import measure
from app.services.privacy.bounds import round_bounds
from app.services.privacy.classify import Confidence, PiiKind, classify_column
from app.services.profiling.profile import profile_files

# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "column,values,expected",
    [
        ("email", ["a@b.com", "c@d.co.uk"], PiiKind.EMAIL_ADDRESS),
        ("full_name", ["Priya Sharma", "Rahul Verma"], PiiKind.PERSON_NAME),
        ("phone", ["+91-9812345678", "020 7946 0958"], PiiKind.PHONE_NUMBER),
        ("ssn", ["123-45-6789", "987-65-4321"], PiiKind.SSN),
        ("client_ip", ["10.0.0.1", "8.8.8.8"], PiiKind.IP_ADDRESS),
        ("pan_number", ["ABCDE1234F", "XYZAB9999Z"], PiiKind.PAN),
        ("dob", ["1988-04-12", "1975-11-30"], PiiKind.DATE_OF_BIRTH),
        ("shipping_address", ["221B Baker Street", "10 Downing Street"], PiiKind.STREET_ADDRESS),
    ],
)
def test_recognises_common_personal_data(column, values, expected):
    finding = classify_column(column, values)
    assert finding is not None
    assert finding.kind is expected
    assert finding.confidence is Confidence.HIGH


@pytest.mark.parametrize(
    "column,values",
    [
        ("company_name", ["Acme Ltd", "Globex Inc"]),
        ("product_name", ["Widget Pro", "Gadget X"]),
        ("account_name", ["Savings", "Current"]),
        ("status", ["active", "banned"]),
        ("order_id", ["1001", "1002"]),
        ("created_at", ["2024-04-12", "2024-11-30"]),
        ("notes", ["called back", "follow up"]),
    ],
)
def test_ordinary_business_columns_are_not_flagged(column, values):
    assert classify_column(column, values) is None


def test_values_win_when_the_column_name_disagrees():
    """A column called `phone` full of email addresses is an email column.
    The finding says so, because a disagreement is worth a human noticing."""
    finding = classify_column("phone", ["a@b.com", "c@d.com", "e@f.com"])
    assert finding is not None
    assert finding.kind is PiiKind.EMAIL_ADDRESS
    assert "though the column name suggests" in finding.reason


def test_a_person_name_needs_the_column_name_to_agree():
    """Regression: `company_name` was redacted as person names, because
    "Acme Ltd" matches a capitalised-words pattern exactly as well as
    "Priya Sharma" does. Values alone can no longer establish a person."""
    assert classify_column("vendor", ["Acme Ltd", "Globex Inc"]) is None
    named = classify_column("full_name", ["Priya Sharma", "Rahul Verma"])
    assert named is not None and named.kind is PiiKind.PERSON_NAME


def test_an_all_null_column_is_judged_on_its_name_alone_and_not_redacted():
    finding = classify_column("email", [])
    assert finding is not None
    assert finding.kind is PiiKind.EMAIL_ADDRESS
    # Name-only evidence must not trigger automatic redaction.
    assert finding.confidence is Confidence.MEDIUM
    assert finding.should_redact is False


def test_a_finding_never_quotes_the_value_it_matched():
    """The reason goes into a compliance report. A report that repeats the
    personal data it found would defeat its own purpose."""
    finding = classify_column("email", ["priya.sharma@example.com"] * 5)
    assert finding is not None
    assert "priya" not in finding.reason.lower()


@pytest.mark.parametrize(
    "column,values",
    [
        ("income", ["36578.234", "91234.5", "120000.75"]),
        ("salary", ["4451382", "360672", "1200000"]),
        ("amount", ["1999.50", "87654.32"]),
    ],
)
def test_numeric_columns_are_not_mistaken_for_phone_numbers(column, values):
    """Regression: a float rendered as "36578.234" is digits with a
    separator and 8 digits in it, which satisfied the phone-number pattern
    exactly — an entire income column was classified as phone numbers and
    redacted. Text-shaped patterns are no longer applied to numbers."""
    assert classify_column(column, values, numeric=True) is None


def test_numeric_personal_data_is_still_caught_by_name():
    finding = classify_column("mobile", ["9812345678", "9876543210"], numeric=True)
    assert finding is not None
    assert finding.kind is PiiKind.PHONE_NUMBER


def test_a_card_number_is_caught_even_stored_as_a_number():
    """Luhn survives the text/number distinction, so it stays enabled for
    numeric columns where every other pattern is suppressed."""
    finding = classify_column("payment_ref", ["4532015112830366", "5425233430109903"], numeric=True)
    assert finding is not None
    assert finding.kind is PiiKind.PAYMENT_CARD


# --------------------------------------------------------------------------
# Redaction during profiling
# --------------------------------------------------------------------------


def _staff_csv(rows: int = 40) -> bytes:
    random.seed(3)
    names = ["Priya Sharma", "Rahul Verma", "Anita Desai", "Vikram Rao"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "full_name", "email", "phone", "salary"])
    for index in range(rows):
        name = random.choice(names)
        writer.writerow(
            [
                index + 1,
                name,
                name.split()[0].lower() + "@acme.com",
                "+91-98" + str(random.randint(10**7, 10**8 - 1)),
                random.randint(300000, 4500000),
            ]
        )
    return buf.getvalue().encode()


def test_profiling_never_copies_a_personal_value_into_the_template():
    """The whole point of Phase 10. Before it, profiling a staff file put
    real names and real email addresses into the project as enum values."""
    result, _ = profile_files([("staff.csv", _staff_csv())], max_rows=5000)
    serialised = result.template.model_dump_json()
    for leaked in ("Priya Sharma", "priya@acme.com", "Rahul Verma", "rahul@acme.com"):
        assert leaked not in serialised


def test_personal_columns_become_synthetic_generators():
    result, _ = profile_files([("staff.csv", _staff_csv())], max_rows=5000)
    fields = {f.name: f for f in result.template.entities[0].fields}
    assert fields["full_name"].preset == "person_name"
    assert fields["email"].preset == "email_address"
    assert fields["phone"].preset == "phone_number"
    # ...and carry no observed data of any kind.
    for name in ("full_name", "email", "phone"):
        assert fields[name].enum_values is None
        assert fields[name].min_value is None


def test_redaction_is_reported_not_silent():
    result, _ = profile_files([("staff.csv", _staff_csv())], max_rows=5000)
    assert any("full_name" in w and "person_name" in w for w in result.warnings)


def test_a_non_personal_column_still_learns_its_shape():
    """Redaction must not become a blunt instrument — the columns that
    aren't personal data still get profiled normally."""
    result, _ = profile_files([("staff.csv", _staff_csv())], max_rows=5000)
    fields = {f.name: f for f in result.template.entities[0].fields}
    assert fields["salary"].formula is not None
    assert fields["salary"].preset is None


# --------------------------------------------------------------------------
# Numeric bounds
# --------------------------------------------------------------------------


def test_observed_extremes_do_not_survive_into_a_range():
    """`uniform(360672, 4451382)` names the exact salary of the lowest- and
    highest-paid person in the sample."""
    result, _ = profile_files([("staff.csv", _staff_csv())], max_rows=5000)
    formula = {f.name: f for f in result.template.entities[0].fields}["salary"].formula
    assert "360672" not in formula
    assert "4451382" not in formula


def test_rounding_only_ever_widens():
    for low, high in [(360672, 4451382), (18, 90), (0.5, 9.87), (1, 40)]:
        rounded_low, rounded_high = round_bounds(low, high)
        assert rounded_low <= low
        assert rounded_high >= high


def test_degenerate_ranges_are_left_alone():
    assert round_bounds(5, 5) == (5, 5)
    assert round_bounds(10, 9) == (10, 9)


# --------------------------------------------------------------------------
# Secret encryption at rest
# --------------------------------------------------------------------------


def test_a_secret_round_trips():
    assert decrypt_secret(encrypt_secret("s3cret-p@ss")) == "s3cret-p@ss"


def test_the_plaintext_is_not_present_in_the_stored_value():
    stored = encrypt_secret("hunter2-is-the-password")
    assert "hunter2" not in stored
    assert stored.startswith(PREFIX)


def test_the_same_secret_encrypts_differently_each_time():
    """Otherwise two connections sharing a password would be visibly equal
    in the table."""
    assert encrypt_secret("same") != encrypt_secret("same")


def test_plaintext_written_before_encryption_existed_is_still_readable():
    """Makes the migration safe to run in either order, and a half-migrated
    table work rather than crash."""
    assert decrypt_secret("legacy-plaintext") == "legacy-plaintext"
    assert is_encrypted("legacy-plaintext") is False


def test_an_empty_secret_stays_empty():
    assert encrypt_secret("") == ""


def test_a_changed_secret_key_fails_loudly(monkeypatch):
    """Silently returning "" would surface as a confusing auth failure a
    long way from the actual cause."""
    stored = encrypt_secret("original")
    secrets._fernet.cache_clear()
    monkeypatch.setattr(secrets.settings, "SECRET_KEY", "an-entirely-different-key")
    try:
        with pytest.raises(SecretDecryptionError):
            decrypt_secret(stored)
    finally:
        secrets._fernet.cache_clear()


def test_a_tampered_value_is_rejected_rather_than_decrypted(monkeypatch):
    """Fernet is authenticated, so an edited ciphertext fails instead of
    decrypting to garbage that then gets used as a password."""
    stored = encrypt_secret("original")
    tampered = stored[:-4] + ("aaaa" if not stored.endswith("aaaa") else "bbbb")
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(tampered)


# --------------------------------------------------------------------------
# k-anonymity / l-diversity
# --------------------------------------------------------------------------


def _grouped_rows():
    """Three cities x two plans, two rows each — k is 2 on (city, plan)."""
    return [
        {"city": city, "plan": plan, "diagnosis": diagnosis}
        for city in ("Pune", "Delhi", "Mumbai")
        for plan, diagnosis in [("free", "flu"), ("free", "cold"), ("pro", "flu"), ("pro", "cold")]
    ]


def test_k_is_the_size_of_the_smallest_quasi_identifier_group():
    report = measure(_grouped_rows(), ["city", "plan"])
    assert report.k == 2
    assert report.groups == 6


def test_fewer_quasi_identifiers_give_larger_groups():
    """The point of the measure: identifiability depends on how much the
    attacker knows, not on the data alone."""
    assert measure(_grouped_rows(), ["city"]).k == 4
    assert measure(_grouped_rows(), ["city", "plan"]).k == 2


def test_a_single_rare_combination_drops_k_to_one_and_fails():
    rows = [*_grouped_rows(), {"city": "Kochi", "plan": "enterprise", "diagnosis": "rare"}]
    report = measure(rows, ["city", "plan"], k_threshold=5)
    assert report.k == 1
    assert report.passes is False
    assert report.smallest_groups[0]["values"] == {"city": "Kochi", "plan": "enterprise"}
    assert report.smallest_groups[0]["rows"] == 1


def test_l_diversity_needs_a_sensitive_field_and_is_skipped_without_one():
    with_sensitive = measure(_grouped_rows(), ["city", "plan"], sensitive_field="diagnosis")
    assert with_sensitive.l_diversity == 2
    without = measure(_grouped_rows(), ["city", "plan"])
    assert without.l_diversity is None
    # No sensitive field named means l cannot fail the report.
    assert without.l_passes is True


def test_a_group_with_one_sensitive_value_fails_l_even_when_k_passes():
    """k says the group is big enough to hide in; l says everyone in it
    shares the same secret, so hiding in it reveals nothing."""
    rows = [{"city": "Pune", "plan": "pro", "diagnosis": "hiv"} for _ in range(20)]
    report = measure(rows, ["city", "plan"], sensitive_field="diagnosis", k_threshold=5)
    assert report.k_passes is True
    assert report.l_diversity == 1
    assert report.l_passes is False
    assert report.passes is False


def test_measuring_nothing_is_not_an_error():
    report = measure([], ["city"])
    assert report.total_rows == 0
    assert report.summary() == "No rows to measure."


def test_quasi_identifiers_are_required():
    with pytest.raises(ValueError):
        measure(_grouped_rows(), [])


def test_values_of_different_types_group_together():
    """A CSV round-trip turns 1 into "1"; both identify the same person."""
    report = measure([{"zone": 1}, {"zone": "1"}], ["zone"])
    assert report.groups == 1
    assert report.k == 2


def test_a_passing_summary_does_not_read_as_a_guarantee():
    report = measure(_grouped_rows(), ["city"], k_threshold=2)
    assert report.passes is True
    # It states what was measured, not that the data is anonymous.
    assert "anonymous" not in report.summary().lower()
