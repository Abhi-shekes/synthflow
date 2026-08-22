"""Validates a GeoRoute's lat/lon columns and interpolates position along
the route — see app.models.geo_route for the full design and
app.services.generator for how a field's value comes from this.
"""

from typing import Any


class GeoRouteError(ValueError):
    pass


def validate_route_columns(rows: list[dict[str, Any]], lat_column: str, lon_column: str) -> None:
    if not rows:
        raise GeoRouteError("Lookup table has no rows to form a route")
    for row in rows:
        for column in (lat_column, lon_column):
            if not isinstance(row.get(column), (int, float)):
                raise GeoRouteError(f"Every row's '{column}' value must be a real number")


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def generate_geo_point(
    rows: list[dict[str, Any]], lat_column: str, lon_column: str, position: int, count: int
) -> dict[str, float]:
    """The field's value at `position` out of `count` rows in this batch:
    linear interpolation between the two waypoints bounding that fractional
    position along the route (position 0 is the first waypoint, position
    count-1 the last, regardless of how many waypoints the route actually
    has — a 5-waypoint route sampled into 200 rows produces 200 smoothly
    interpolated points along that polyline). A single-waypoint route
    returns that point for every row.

    A position past the end of the batch **wraps**, so the vehicle drives
    the route again rather than parking at the last waypoint. That only
    happens under Phase 13 continuity (`iter_rows(start_position=...)`),
    where the position keeps climbing across calls; within a single batch
    position never reaches `count`, so the modulo is a no-op and existing
    behaviour is unchanged. Clamping instead would have frozen every vehicle
    on its destination from the second tick onward, which is not what "a
    vehicle pinging its position along a fixed route" looks like over time.
    """
    if len(rows) == 1:
        return {"lat": rows[0][lat_column], "lon": rows[0][lon_column]}

    fraction = (position % count if count else 0) / max(count - 1, 1)
    fraction = min(max(fraction, 0.0), 1.0)
    segment_progress = fraction * (len(rows) - 1)
    segment_index = min(int(segment_progress), len(rows) - 2)
    local_t = segment_progress - segment_index

    a, b = rows[segment_index], rows[segment_index + 1]
    return {
        "lat": round(_lerp(a[lat_column], b[lat_column], local_t), 6),
        "lon": round(_lerp(a[lon_column], b[lon_column], local_t), 6),
    }
