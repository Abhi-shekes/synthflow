"""Decide whether a column holds personal data, and which kind.

Used by app.services.profiling.profile to stop real values reaching a
generated project. Two independent signals, because either alone is wrong
often enough to matter:

  * the column *name* — cheap, and the only signal available for a column
    whose values are all missing, but easily fooled (`account_name` is not
    a person, `contact` could be anything)
  * the column *values* — authoritative when they match a strict shape
    (an email address is unmistakable), useless for free text where a
    person's name looks like any other short string

Names alone therefore never reach `HIGH`. A value match can, because
matching 90% of a column against the email pattern is not a coincidence.
The distinction matters: `HIGH` findings are redacted automatically and
`MEDIUM`/`LOW` ones are only reported, so a false positive at LOW costs a
line in a report while a false positive at HIGH silently replaces a column
the user cared about.

Deliberately regex and keywords, not a model. It runs on every profiled
column, has to be explainable to whoever reads the compliance report, and
must work in an air-gapped install — the same reasoning as Phase 9.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

# Only a sample of a column's values is tested — the patterns are strict
# enough that 200 rows settle it, and profiling runs on every import.
MAX_VALUES_TESTED = 200

# Share of tested values that must match a pattern before the column is
# called that kind. Deliberately below 1.0: real columns have typos, empty
# strings and the odd "N/A", and a single bad row should not hide an email
# column.
VALUE_MATCH_THRESHOLD = 0.8

# A name hint alone gives MEDIUM. Combined with even weak value agreement
# it becomes HIGH — that combination is what most real PII columns look
# like, since a column called `email` full of addresses matches both.
NAME_AGREEMENT_THRESHOLD = 0.5


class Confidence(enum.StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PiiKind(enum.StrEnum):
    """What was found. Values match app.models.field.PiiPreset where a
    direct synthetic replacement exists, so the profiler can swap one for
    the other without a lookup table."""

    PERSON_NAME = "person_name"
    EMAIL_ADDRESS = "email_address"
    PHONE_NUMBER = "phone_number"
    STREET_ADDRESS = "street_address"
    POSTCODE = "postcode"
    PAYMENT_CARD = "payment_card"
    SSN = "ssn"
    AADHAAR = "aadhaar"
    PAN = "pan"
    IP_ADDRESS = "ip_address"
    USERNAME = "username"
    DATE_OF_BIRTH = "date_of_birth"


@dataclass
class PiiFinding:
    kind: PiiKind
    confidence: Confidence
    # Human-readable reason, quoted verbatim into the privacy report. Never
    # contains an observed value — a report that quotes the PII it found
    # would defeat its own purpose.
    reason: str
    matched_ratio: float = 0.0

    @property
    def should_redact(self) -> bool:
        """Only HIGH is acted on automatically. Anything less is surfaced to
        the user to decide, because silently replacing a column on a guess
        is its own kind of damage."""
        return self.confidence is Confidence.HIGH


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_SSN_RE = re.compile(r"^\d{3}-\d{2}-\d{4}$")
_AADHAAR_RE = re.compile(r"^[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}$")
_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
_POSTCODE_RE = re.compile(r"^(\d{5}(-\d{4})?|\d{6}|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})$", re.I)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].*)?$")
_PERSON_NAME_RE = re.compile(r"^[A-Z][a-z'\-]+(?: [A-Z][a-z'\-]+){1,3}$")
_STREET_RE = re.compile(
    r"\d+\s+\w+.*\b(street|st|road|rd|avenue|ave|lane|ln|drive|dr|boulevard|blvd|way|court|ct)\b",
    re.I,
)
# Digits with optional separators, 7-15 long. Phone numbers vary enough by
# country that anything stricter mostly rejects real ones.
_PHONE_RE = re.compile(r"^\+?[\d][\d\s\-().]{5,18}\d$")


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def _luhn_ok(value: str) -> bool:
    digits = _digits(value)
    if not 12 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _is_phone(value: str) -> bool:
    """Checked after payment card, and requires 7-15 digits, so a 16-digit
    card number is not also reported as a phone number.

    ISO dates are excluded explicitly: `1988-04-12` is digits separated by
    dashes with 8 digits in it, which otherwise satisfies every part of the
    phone test. That misclassified a whole `dob` column as phone numbers —
    the values got redacted either way, but the report would have told a
    compliance reviewer the wrong thing about what the column held."""
    if _DATE_RE.match(value):
        return False
    return bool(_PHONE_RE.match(value)) and 7 <= len(_digits(value)) <= 15


# Order matters: the first kind whose predicate passes the threshold wins,
# so the strict, unmistakable shapes are tested before the loose ones. A
# payment card would otherwise also satisfy the phone-number pattern.
_VALUE_TESTS: list[tuple[PiiKind, object]] = [
    (PiiKind.EMAIL_ADDRESS, lambda v: bool(_EMAIL_RE.match(v))),
    (
        PiiKind.IP_ADDRESS,
        lambda v: bool(_IPV4_RE.match(v)) and all(int(p) < 256 for p in v.split(".")),
    ),
    (PiiKind.SSN, lambda v: bool(_SSN_RE.match(v))),
    (PiiKind.PAN, lambda v: bool(_PAN_RE.match(v))),
    (PiiKind.AADHAAR, lambda v: bool(_AADHAAR_RE.match(v))),
    (PiiKind.PAYMENT_CARD, _luhn_ok),
    (PiiKind.STREET_ADDRESS, lambda v: bool(_STREET_RE.search(v))),
    # Before PHONE_NUMBER: see the ISO-date note in _is_phone. A bare date
    # column is only called a birth date when the name also says so, which
    # is why this predicate is deliberately not just "looks like a date".
    (PiiKind.PHONE_NUMBER, _is_phone),
    # PERSON_NAME is deliberately absent. "Two or three capitalised words"
    # describes "Priya Sharma" and "Acme Ltd" equally well, so matching it
    # on values alone redacted every company- and product-name column that
    # the name exclusions below didn't happen to list. A person's name has
    # no distinguishing shape, so it is established by the column *name*
    # plus loose value agreement (`_weak_agreement`) instead — which is
    # how a human identifies one of these columns too.
]

# Substring hints on the column name. Checked longest-first so `first_name`
# is not swallowed by `name`.
_NAME_HINTS: dict[str, PiiKind] = {
    "email": PiiKind.EMAIL_ADDRESS,
    "e_mail": PiiKind.EMAIL_ADDRESS,
    "mail": PiiKind.EMAIL_ADDRESS,
    "phone": PiiKind.PHONE_NUMBER,
    "mobile": PiiKind.PHONE_NUMBER,
    "telephone": PiiKind.PHONE_NUMBER,
    "contact_number": PiiKind.PHONE_NUMBER,
    "full_name": PiiKind.PERSON_NAME,
    "first_name": PiiKind.PERSON_NAME,
    "last_name": PiiKind.PERSON_NAME,
    "surname": PiiKind.PERSON_NAME,
    "customer_name": PiiKind.PERSON_NAME,
    "person_name": PiiKind.PERSON_NAME,
    "name": PiiKind.PERSON_NAME,
    "address": PiiKind.STREET_ADDRESS,
    "street": PiiKind.STREET_ADDRESS,
    "postcode": PiiKind.POSTCODE,
    "postal_code": PiiKind.POSTCODE,
    "zip": PiiKind.POSTCODE,
    "pincode": PiiKind.POSTCODE,
    "card_number": PiiKind.PAYMENT_CARD,
    "credit_card": PiiKind.PAYMENT_CARD,
    "ccnum": PiiKind.PAYMENT_CARD,
    "ssn": PiiKind.SSN,
    "social_security": PiiKind.SSN,
    "aadhaar": PiiKind.AADHAAR,
    "aadhar": PiiKind.AADHAAR,
    "pan_number": PiiKind.PAN,
    "ip_address": PiiKind.IP_ADDRESS,
    "ip_addr": PiiKind.IP_ADDRESS,
    "client_ip": PiiKind.IP_ADDRESS,
    "username": PiiKind.USERNAME,
    "user_name": PiiKind.USERNAME,
    "login": PiiKind.USERNAME,
    "date_of_birth": PiiKind.DATE_OF_BIRTH,
    "dob": PiiKind.DATE_OF_BIRTH,
    "birth_date": PiiKind.DATE_OF_BIRTH,
    "birthdate": PiiKind.DATE_OF_BIRTH,
}

# Names that contain a hint substring but are not about a person. Checked
# before the hints, because `company_name`/`product_name` ending up as
# PERSON_NAME would redact ordinary business columns.
_NAME_EXCLUSIONS = (
    "company_name",
    "organisation_name",
    "organization_name",
    "product_name",
    "brand_name",
    "file_name",
    "filename",
    "table_name",
    "column_name",
    "field_name",
    "event_name",
    "domain_name",
    "host_name",
    "hostname",
    "service_name",
    "project_name",
    "account_name",
    "bank_name",
    "city_name",
    "country_name",
    "state_name",
)


def _name_hint(column: str) -> PiiKind | None:
    normalised = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_")
    if any(excluded in normalised for excluded in _NAME_EXCLUSIONS):
        return None
    for hint in sorted(_NAME_HINTS, key=len, reverse=True):
        if hint in normalised:
            return _NAME_HINTS[hint]
    return None


# The only value tests that mean anything for a column of plain numbers.
# A card number keeps its Luhn check whether it is stored as text or as an
# integer, and 12-19 digits passing Luhn at an 80% rate is not chance.
# Everything else in `_VALUE_TESTS` assumes text and produces false
# positives on ordinary numeric data — see `_best_value_match`.
_NUMERIC_SAFE_KINDS = frozenset({PiiKind.PAYMENT_CARD})


def _best_value_match(values: list[str], *, numeric: bool) -> tuple[PiiKind, float] | None:
    """Find the kind whose pattern most of these values match.

    On a *numeric* column almost every pattern here is a trap. A float
    rendered as "36578.234" is digits with a separator and 8 digits in it,
    which satisfies the phone-number test exactly — that classified an
    entire income column as phone numbers and redacted it. Numbers are
    therefore tested only against `_NUMERIC_SAFE_KINDS`, and a numeric
    column that really does hold personal data is caught by its name
    instead, which is how such columns are found in practice anyway.
    """
    tested = [v.strip() for v in values[:MAX_VALUES_TESTED] if v and v.strip()]
    if not tested:
        return None
    for kind, predicate in _VALUE_TESTS:
        if numeric and kind not in _NUMERIC_SAFE_KINDS:
            continue
        matched = sum(1 for value in tested if predicate(value))  # type: ignore[operator]
        ratio = matched / len(tested)
        if ratio >= VALUE_MATCH_THRESHOLD:
            return kind, ratio
    return None


def classify_column(column: str, values: list[str], *, numeric: bool = False) -> PiiFinding | None:
    """Classify one column. Returns None when nothing suggests personal data.

    `values` should be the non-missing values as strings; pass an empty list
    for a column that is entirely null, in which case only the name is used.
    Set `numeric` for a column the profiler inferred as integer or float —
    it suppresses the text-shaped patterns, which misfire badly on numbers.
    """
    hint = _name_hint(column)
    match = _best_value_match(values, numeric=numeric)

    if match is not None:
        kind, ratio = match
        if hint is kind:
            return PiiFinding(
                kind,
                Confidence.HIGH,
                f"column name and {ratio:.0%} of sampled values both indicate {kind.value}",
                ratio,
            )
        if hint is not None:
            # Name and values disagree. Trust the values — a column called
            # `contact` full of email addresses is an email column — but say
            # so, because a disagreement is worth a human's attention.
            return PiiFinding(
                kind,
                Confidence.HIGH,
                f"{ratio:.0%} of sampled values match {kind.value}, "
                f"though the column name suggests {hint.value}",
                ratio,
            )
        return PiiFinding(
            kind, Confidence.HIGH, f"{ratio:.0%} of sampled values match {kind.value}", ratio
        )

    if hint is not None:
        # Free-text names land here: `full_name` whose values are real names
        # that the loose name regex did not clear the threshold on. Reported,
        # not redacted.
        weak = _weak_agreement(hint, values)
        if weak >= NAME_AGREEMENT_THRESHOLD:
            return PiiFinding(
                hint,
                Confidence.HIGH,
                f"column name indicates {hint.value}, and {weak:.0%} of "
                f"sampled values are consistent with it",
                weak,
            )
        return PiiFinding(hint, Confidence.MEDIUM, f"column name indicates {hint.value}", weak)

    return None


def _weak_agreement(kind: PiiKind, values: list[str]) -> float:
    """How consistent the values are with `kind`, using a looser test than
    `_VALUE_TESTS`. Only consulted once a name hint already exists, so it
    only has to separate "plausible" from "clearly not" — a `dob` column of
    ISO dates, or a `full_name` column of short capitalised strings."""
    tested = [v.strip() for v in values[:MAX_VALUES_TESTED] if v and v.strip()]
    if not tested:
        return 0.0

    if kind is PiiKind.DATE_OF_BIRTH:
        predicate = lambda v: bool(_DATE_RE.match(v))  # noqa: E731
    elif kind is PiiKind.PERSON_NAME:
        predicate = lambda v: 2 <= len(v) <= 60 and any(c.isalpha() for c in v)  # noqa: E731
    elif kind is PiiKind.POSTCODE:
        predicate = lambda v: bool(_POSTCODE_RE.match(v))  # noqa: E731
    elif kind is PiiKind.USERNAME:
        predicate = lambda v: 2 <= len(v) <= 40 and " " not in v  # noqa: E731
    elif kind in (PiiKind.PHONE_NUMBER, PiiKind.SSN, PiiKind.AADHAAR, PiiKind.PAYMENT_CARD):
        predicate = lambda v: len(_digits(v)) >= 6  # noqa: E731
    elif kind is PiiKind.STREET_ADDRESS:
        predicate = lambda v: len(v) >= 8 and any(c.isdigit() for c in v)  # noqa: E731
    else:
        predicate = lambda v: True  # noqa: E731

    return sum(1 for value in tested if predicate(value)) / len(tested)
