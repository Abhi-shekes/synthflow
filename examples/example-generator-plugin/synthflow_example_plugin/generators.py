"""Example SynthFlow generator plugin.

Demonstrates the contract every entry under the "synthflow.generators"
entry-point group must follow: a zero-argument callable returning a
JSON-serializable value (str, int, float, bool, list, or dict). It gets
called once per row, with no access to the rest of the row being
generated — the same contract the built-in presets follow (see the main
repo's app/services/identifier_generators.py and log_generators.py).
"""

import random
import string


def license_plate() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = "".join(random.choices(string.digits, k=2))
    suffix = "".join(random.choices(string.ascii_uppercase, k=3))
    return f"{letters}{digits} {suffix}"
