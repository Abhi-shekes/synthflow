"""Synthetic stand-ins for personal data, for a STRING field with a `preset`
set (see app.models.field.PiiPreset).

These exist so that profiling a real file never has to copy a real value
into a project. When app.services.privacy.classify decides a column holds
people's names, the profiler points the field at `person_name` here instead
of emitting the observed values as an enum — see
app.services.profiling.profile._apply_privacy.

Every value is fabricated by Faker. Nothing here reverses, decrypts or
derives from any input: a generated name has no relationship to the name it
replaced. That is the point — a format-preserving *pseudonym* that maps back
to an individual is still personal data, and this module deliberately does
not offer one. Consistent-mapping tokenisation is a different feature with a
different risk profile.

Payment card numbers carry a real Luhn check digit because the whole reason
to generate one is to exercise a validator, and the IIN ranges Faker draws
from are the standard test ranges — they do not correspond to an issued
card. National identifiers follow published structural rules only; see the
note on each generator.
"""

import random
import string

from faker import Faker

faker = Faker()

_AADHAAR_FIRST = "23456789"  # a real Aadhaar never starts 0 or 1


def _person_name() -> str:
    return faker.name()


def _first_name() -> str:
    return faker.first_name()


def _last_name() -> str:
    return faker.last_name()


def _email_address() -> str:
    """A free-mail-shaped address. `business_email` in
    app.services.identifier_generators covers the corporate-domain shape;
    this is the one a customer table usually holds."""
    return faker.free_email()


def _phone_number() -> str:
    return faker.phone_number()


def _street_address() -> str:
    return faker.street_address()


def _full_address() -> str:
    return faker.address().replace("\n", ", ")


def _postcode() -> str:
    return faker.postcode()


def _city() -> str:
    return faker.city()


def _payment_card() -> str:
    """A Luhn-valid number from Faker's test IIN ranges. Valid-looking on
    purpose: the use case is testing a payment form's validation, and a
    number that fails Luhn tests nothing."""
    return faker.credit_card_number()


def _ssn() -> str:
    """US-shaped. Faker already excludes the invalid area numbers (000, 666,
    900-999), so this will not collide with a real issued SSN pattern."""
    return faker.ssn()


def _aadhaar() -> str:
    """India's 12-digit UID, formatted in the usual 4-4-4 groups. Structural
    rules only: it never starts with 0 or 1. The real Verhoeff check digit
    is *not* computed -- a number that passes a genuine Aadhaar validator is
    not something this repo should manufacture, and format testing does not
    need it. `pan` in app.services.identifier_generators is the equivalent
    for India's tax id."""
    digits = _AADHAAR_FIRST[random.randrange(len(_AADHAAR_FIRST))]
    digits += "".join(random.choices(string.digits, k=11))
    return f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"


def _ip_address() -> str:
    return faker.ipv4()


def _username() -> str:
    return faker.user_name()


def _company_name() -> str:
    return faker.company()


def _date_of_birth() -> str:
    """ISO date for an adult. A DATE field with a min/max is the better tool
    when you want a specific span -- this preset exists for the common case
    where a profiled `dob` column should stop carrying real birth dates."""
    return faker.date_of_birth(minimum_age=18, maximum_age=90).isoformat()


_GENERATORS = {
    "person_name": _person_name,
    "first_name": _first_name,
    "last_name": _last_name,
    "email_address": _email_address,
    "phone_number": _phone_number,
    "street_address": _street_address,
    "full_address": _full_address,
    "postcode": _postcode,
    "city": _city,
    "payment_card": _payment_card,
    "ssn": _ssn,
    "aadhaar": _aadhaar,
    "ip_address": _ip_address,
    "username": _username,
    "company_name": _company_name,
    "date_of_birth": _date_of_birth,
}


def generate_pii(preset: str) -> str:
    """Produce one synthetic value for the named preset.

    Mirrors app.services.identifier_generators.generate_identifier, and is
    registered into the same registry — see app.services.plugins.
    """
    try:
        return _GENERATORS[preset]()
    except KeyError:
        raise ValueError(f"Unknown PII preset: {preset}") from None
