"""Domain-specific identifier/code text for a STRING field with a `preset`
set (see app.models.field.IdentifierPreset). Every value here is randomly
fabricated — nothing here talks to a real government registry, vehicle
database, or device/carrier network. Formats follow the real-world
character-position rules closely enough to pass a naive format check
(length, charset, structural check digits where the algorithm is simple
and well-known), but check digits that depend on non-public or disputed
algorithms (GSTIN's) are left as a plausible random character rather than
guessed at — see the GSTIN generator below.
"""

import base64
import io
import random
import string
import uuid

import qrcode
from faker import Faker

faker = Faker()

_PAN_LETTERS = string.ascii_uppercase
_PAN_DIGITS = string.digits
_VIN_CHARS = "".join(c for c in string.ascii_uppercase + string.digits if c not in "IOQ")
_ALNUM_UPPER = string.ascii_uppercase + string.digits


def _pan() -> str:
    letters = "".join(random.choices(_PAN_LETTERS, k=5))
    digits = "".join(random.choices(_PAN_DIGITS, k=4))
    check = random.choice(_PAN_LETTERS)
    return f"{letters}{digits}{check}"


def _vin() -> str:
    return "".join(random.choices(_VIN_CHARS, k=17))


def _imei() -> str:
    # TAC (8 digits) + serial number (6 digits) + Luhn check digit (1 digit),
    # the real IMEI structure — the Luhn algorithm is public and simple
    # enough to get right, unlike GSTIN's checksum below.
    body = "".join(random.choices(string.digits, k=14))
    total = 0
    for i, ch in enumerate(reversed(body)):
        digit = int(ch)
        if i % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check_digit = (10 - (total % 10)) % 10
    return f"{body}{check_digit}"


def _gstin() -> str:
    state_code = f"{random.randint(1, 37):02d}"
    entity_number = random.choice(string.digits[1:])  # 1-9
    check = random.choice(_ALNUM_UPPER)
    return f"{state_code}{_pan()}{entity_number}Z{check}"


def _qr_code() -> str:
    payload = f"https://example.com/id/{uuid.uuid4()}"
    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _business_email() -> str:
    first = faker.first_name().lower()
    last = faker.last_name().lower()
    return f"{first}.{last}@{faker.domain_name()}"


_IDENTIFIER_PRESETS = {
    "pan": _pan,
    "vin": _vin,
    "imei": _imei,
    "gstin": _gstin,
    "qr_code": _qr_code,
    "business_email": _business_email,
}


def generate_identifier(preset: str) -> str:
    return _IDENTIFIER_PRESETS[preset]()
