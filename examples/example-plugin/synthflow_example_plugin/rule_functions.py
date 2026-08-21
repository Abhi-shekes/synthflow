"""Example SynthFlow rule-function plugin.

Demonstrates the contract every entry under the "synthflow.rule_functions"
entry-point group must follow: any callable, with any positional
arguments. Once installed, it's callable by name from inside a rule
condition, an event-trigger condition, or a formula field — the same way
the built-in noise()/uniform() already are (see the main repo's
app/services/expressions.py).
"""

from datetime import date


def is_business_day(iso_date: str) -> bool:
    return date.fromisoformat(iso_date).weekday() < 5
