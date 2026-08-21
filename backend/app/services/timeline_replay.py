"""Validates a TimelineReplay's timestamp column and builds its playback
schedule — see app.api.routes.timeline_replays for the public WS loop that
walks it against a clock.
"""

from datetime import datetime
from typing import Any


class TimelineReplayError(ValueError):
    pass


def parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TimelineReplayError("Timestamp column values must be strings")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise TimelineReplayError(f"'{value}' is not a valid ISO-8601 timestamp") from exc


def validate_timestamp_column(rows: list[dict[str, Any]], column: str) -> None:
    if not rows:
        raise TimelineReplayError("Lookup table has no rows to replay")
    for row in rows:
        if column not in row:
            raise TimelineReplayError(f"Not every row has a '{column}' value")
        parse_timestamp(row[column])


def build_schedule(rows: list[dict[str, Any]], column: str) -> list[dict[str, Any]]:
    """Rows in their actual replay order — ascending by timestamp column,
    regardless of upload order."""
    return sorted(rows, key=lambda r: parse_timestamp(r[column]))
