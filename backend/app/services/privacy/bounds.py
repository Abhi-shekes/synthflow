"""Round observed numeric bounds outward, so a fitted range does not
publish two real records' exact values.

`uniform(360672, 4451382)` learned from a salary column names the exact pay
of the lowest and highest earner in the sample. Neither is "personally
identifiable" by pattern — no classifier will ever flag a salary column —
but the maximum of a sensitive column is one of the easiest values in a
dataset to attribute to a person, and it survives into the template as a
literal. Rounding to `uniform(300000, 4500000)` keeps the range useful and
stops it being a disclosure.

Rounding is always **outward**: the interval only ever grows. Narrowing
would exclude real observed values and quietly misrepresent the data, which
is a worse failure than a slightly wide range.

This is a mitigation, not anonymity. It removes exact-value disclosure from
the bounds; it does not make the column anonymous, and it makes no
statistical guarantee. Differential privacy is the thing that would, and it
belongs on the fitting step rather than here.

Note that the granularity scales with the span, so a wide column (salaries)
is rounded heavily while a narrow one (ages 18-90) may not move at all. A
narrow range discloses less by being narrow — the endpoints of an age
column identify far fewer people than the endpoints of a salary column —
but "unchanged" is a real outcome here, not a guarantee of protection.
"""

from __future__ import annotations

import math

# How coarse the rounding is, relative to the span. 1 gives one significant
# digit of granularity (0-4500000 rounds to the nearest 500k... too coarse
# for most columns), 2 gives two (nearest 100k for that span), which keeps
# the range recognisable while removing the exact endpoints.
_GRANULARITY_DIGITS = 2


def round_bounds(low: float, high: float) -> tuple[float, float]:
    """Widen [low, high] to a round-numbered interval containing it.

    Degenerate and tiny ranges are returned unchanged: with a span of zero
    there is nothing to round to, and for a span below 1 the rounding would
    swamp the data.
    """
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return low, high

    span = high - low
    if span < 1:
        return low, high

    step = 10 ** (math.floor(math.log10(span)) - (_GRANULARITY_DIGITS - 1))
    if step <= 0:
        return low, high

    rounded_low = math.floor(low / step) * step
    rounded_high = math.ceil(high / step) * step

    # A whole-number column should not acquire a decimal point from this.
    if float(low).is_integer() and float(high).is_integer():
        return float(round(rounded_low)), float(round(rounded_high))
    return rounded_low, rounded_high
