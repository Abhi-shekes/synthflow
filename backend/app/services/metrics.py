"""Prometheus metrics for the live monitoring dashboard — every metric the
app exposes is defined here, in one place, rather than scattered across
the modules that record them.

Two deliberate design choices worth knowing:

**Label cardinality is bounded on purpose.** Nothing here is labelled by
project, entity, field, or output id — only by a short fixed set of
`source`/`kind` values. Those are user-controlled, unbounded strings: a
label per entity name would both blow up Prometheus' series count and
leak a user's schema names into `/metrics`, which is deliberately
unauthenticated (see app.api.routes.metrics). Bounded labels are what
makes serving that endpoint without auth safe — it exposes counts and
timings, never anyone's data or naming.

**"Active" gauges read existing state instead of being incremented.**
`stream_producers` and `plugin_output_producers` already keep a
module-level `_tasks` registry of live background tasks — that registry
*is* the active-producer count, so these gauges just read `len()` of it
at scrape time via a callback, with zero instrumentation in the
producers themselves and no second source of truth to drift. The one
exception is connected WebSocket clients: there's no registry there (the
handler's own stack frame is the state), so that one is a real
inc/dec gauge in the handler.

Row counting/timing does need call-site instrumentation, since
`generate_rows` has no idea which output is calling it. Rather than
thread a `source` argument through the generation engine, the boundary
that *does* know its identity wraps the call in `generation(source)` —
so app.services.generator stays free of metrics code entirely.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram

# Fixed, bounded label values — see module docstring on why these are
# hardcoded rather than derived from user data.
# TimelineReplay is deliberately absent: it walks an already-uploaded
# lookup table against a clock, it never calls the generation engine.
GENERATION_SOURCES = (
    "api",
    "rest",
    "websocket",
    "kafka",
    "mqtt",
    "plugin",
    "database_push",
)
PRODUCER_KINDS = ("kafka", "mqtt", "plugin")

rows_generated_total = Counter(
    "synthflow_rows_generated_total",
    "Rows produced by the generation engine, by what asked for them.",
    ["source"],
)

generation_errors_total = Counter(
    "synthflow_generation_errors_total",
    "Generation attempts that raised instead of returning rows.",
    ["source"],
)

generation_seconds = Histogram(
    "synthflow_generation_seconds",
    "Wall time spent inside a single generation call.",
    ["source"],
)

output_deliveries_total = Counter(
    "synthflow_output_deliveries_total",
    "Batches successfully handed to a background output (broker or plugin).",
    ["kind"],
)

output_delivery_errors_total = Counter(
    "synthflow_output_delivery_errors_total",
    "Background output deliveries that failed.",
    ["kind"],
)

active_websocket_clients = Gauge(
    "synthflow_active_websocket_clients",
    "WebSocket stream clients currently connected.",
)

active_producers = Gauge(
    "synthflow_active_producers",
    "Background output producer tasks currently running.",
    ["kind"],
)


def _init_label_values() -> None:
    """Create the zero-valued series up front so a dashboard shows
    `0` rather than "No data" for an output kind nobody has used yet —
    Prometheus only knows a labelled series exists once it's been
    touched at least once."""
    for source in GENERATION_SOURCES:
        rows_generated_total.labels(source=source)
        generation_errors_total.labels(source=source)
        generation_seconds.labels(source=source)
    for kind in PRODUCER_KINDS:
        output_deliveries_total.labels(kind=kind)
        output_delivery_errors_total.labels(kind=kind)


def _count_stream_producers(kind: str) -> float:
    # Imported lazily: stream_producers imports this module, so a
    # module-level import here would be circular.
    from app.services import stream_producers

    return float(sum(1 for task_kind in stream_producers.task_kinds() if task_kind == kind))


def _count_plugin_producers() -> float:
    from app.services import plugin_output_producers

    return float(len(plugin_output_producers._tasks))


def init_gauges() -> None:
    """Wire the "active producers" gauges to the existing task registries.
    Called once at app startup (app.main's lifespan)."""
    active_producers.labels(kind="kafka").set_function(lambda: _count_stream_producers("kafka"))
    active_producers.labels(kind="mqtt").set_function(lambda: _count_stream_producers("mqtt"))
    active_producers.labels(kind="plugin").set_function(_count_plugin_producers)
    _init_label_values()


class _GenerationRecorder:
    """Handed to the body of `generation(...)` so it can report how many
    rows the call actually produced — the count isn't knowable until the
    call returns."""

    def __init__(self) -> None:
        self.rows = 0

    def count(self, rows: int) -> None:
        self.rows = rows


@contextmanager
def generation(source: str) -> Iterator[_GenerationRecorder]:
    """Time one generation call, counting its rows on success and an
    error on failure. `source` must be one of GENERATION_SOURCES."""
    recorder = _GenerationRecorder()
    try:
        with generation_seconds.labels(source=source).time():
            yield recorder
    except Exception:
        generation_errors_total.labels(source=source).inc()
        raise
    else:
        if recorder.rows:
            rows_generated_total.labels(source=source).inc(recorder.rows)


def record_delivery(kind: str, batches: int = 1) -> None:
    output_deliveries_total.labels(kind=kind).inc(batches)


def record_delivery_error(kind: str) -> None:
    output_delivery_errors_total.labels(kind=kind).inc()
