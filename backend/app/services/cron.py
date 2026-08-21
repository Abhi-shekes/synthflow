"""A five-field cron parser, just enough to answer "when next, after X?".

Deliberately not a dependency. The full cron ecosystem (croniter and
friends) brings timezone handling, seconds fields, `@reboot`, `L`/`W`/`#`
day specifiers and a lot else; SynthFlow needs one question answered
about standard `minute hour day month weekday` expressions, and owning
~80 readable lines is cheaper than owning a dependency's release cycle
for that.

Supported per field: `*`, a number, `a-b` ranges, `a,b,c` lists, and
`*/n` or `a-b/n` steps — which covers the expressions people actually
write. Anything else is rejected at schedule-creation time with a clear
message rather than silently never firing, which is the failure mode that
matters: a schedule that quietly does nothing is worse than one that
refuses to be created.

Times are naive UTC throughout, matching how the rest of the app stores
timestamps. Local-time schedules would need a timezone column and are
noted in ROADMAP Phase 8 rather than half-implemented here.
"""

from datetime import datetime, timedelta

# (name, low, high) per position in a standard cron expression.
_FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 6),
)

# A year of minutes is the search bound. Any valid expression fires at
# least once a year, so exceeding it means the expression is satisfiable
# in isolation but never as a whole — "31st of February" being the
# classic. Better to say so than to loop forever.
_MAX_SEARCH_MINUTES = 366 * 24 * 60


class CronError(ValueError):
    pass


def _parse_field(raw: str, name: str, low: int, high: int) -> set[int]:
    values: set[int] = set()

    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"Empty value in the {name} field")

        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            if not step_text.isdigit() or int(step_text) < 1:
                raise CronError(f"Invalid step '{step_text}' in the {name} field")
            step = int(step_text)

        if part == "*":
            start, end = low, high
        elif "-" in part.lstrip("-"):
            start_text, _, end_text = part.partition("-")
            if not start_text.isdigit() or not end_text.isdigit():
                raise CronError(f"Invalid range '{part}' in the {name} field")
            start, end = int(start_text), int(end_text)
            if start > end:
                raise CronError(f"Range '{part}' in the {name} field is backwards")
        elif part.isdigit():
            start = end = int(part)
        else:
            raise CronError(f"Could not read '{part}' in the {name} field")

        if start < low or end > high:
            raise CronError(f"The {name} field must be between {low} and {high}, got '{part}'")

        values.update(range(start, end + 1, step))

    return values


def parse(expression: str) -> tuple[set[int], ...]:
    """Validate an expression, returning the allowed values per field.
    Raises CronError with a message suitable for showing a user."""
    parts = expression.split()
    if len(parts) != 5:
        raise CronError(
            f"A cron expression needs 5 fields (minute hour day month weekday), got {len(parts)}"
        )
    return tuple(
        _parse_field(raw, name, low, high)
        for raw, (name, low, high) in zip(parts, _FIELDS, strict=True)
    )


def next_after(expression: str, after: datetime) -> datetime:
    """The first matching minute strictly after `after`."""
    minutes, hours, days, months, weekdays = parse(expression)

    # Start at the next whole minute; a schedule never fires in the past.
    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)

    for _ in range(_MAX_SEARCH_MINUTES):
        # Python's Monday=0 vs cron's Sunday=0.
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.month in months
            and candidate.day in days
            and cron_weekday in weekdays
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise CronError(
        f"'{expression}' never comes round — check the day and month fields "
        f"(for example, February the 31st)"
    )


def describe(expression: str) -> str:
    """A short human summary for the UI. Intentionally rough — it covers
    the common shapes and otherwise falls back to echoing the
    expression, rather than pretending to translate every possibility."""
    parse(expression)
    minute, hour, day, month, weekday = expression.split()

    if (minute, hour, day, month, weekday) == ("*", "*", "*", "*", "*"):
        return "Every minute"
    if (day, month, weekday) == ("*", "*", "*"):
        if hour == "*" and minute.isdigit():
            return f"Hourly, at {minute} minutes past"
        if hour.isdigit() and minute.isdigit():
            return f"Daily at {int(hour):02d}:{int(minute):02d} UTC"
    if minute.isdigit() and hour.isdigit() and weekday.isdigit() and (day, month) == ("*", "*"):
        names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        return f"Every {names[int(weekday)]} at {int(hour):02d}:{int(minute):02d} UTC"
    return f"Cron: {expression}"
