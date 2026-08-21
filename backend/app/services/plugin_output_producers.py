"""In-process background producers for third-party output plugins — the
generic counterpart to app.services.stream_producers (which is Kafka/MQTT
specific, since those have a fixed config shape). Same execution model:
an `asyncio.Task` tracked in a module-level registry, started when a
PluginOutput row is created and cancelled when it's deleted, not resumed
if the backend process restarts, single-process only, bounded retry with
backoff on failure. See stream_producers.py's module docstring for the
full reasoning behind those choices — not repeated here.

An output plugin (see app.services.plugins — the `synthflow.outputs`
entry-point group) only owns delivery: this loop owns pacing
(`events_per_second`) and batch loading, calling the plugin's
`deliver_batch(config, rows)` once per tick. The plugin function can be
sync or async — a plugin author writing a simple "append to a file"
function shouldn't have to know asyncio to do it; a sync function just
runs in a thread (`asyncio.to_thread`) so it can't block the event loop.
"""

import asyncio
import contextlib
import inspect
import logging
from typing import Any
from uuid import UUID

from app.db import session as db_session
from app.models.plugin_output import PluginOutput
from app.services import metrics
from app.services.generator import build_lookup_pools, generate_rows
from app.services.plugins import available_output_plugins

logger = logging.getLogger(__name__)

_tasks: dict[UUID, asyncio.Task] = {}

RETRY_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_FAILURES = 5


def _load_output_sync(
    output_id: UUID,
) -> tuple[list[dict[str, Any]], float, str, dict] | None:
    """One short-lived session, plain data out — same reasoning as
    stream_producers._load_batch_sync, including looking up
    `db_session.SessionLocal` fresh each call so tests can override it.
    Returns None if the output row is gone (deleted mid-run), the signal
    for the calling loop to stop."""
    db = db_session.SessionLocal()
    try:
        output = db.get(PluginOutput, output_id)
        if output is None:
            return None
        entity = output.entity
        with metrics.generation("plugin") as recorder:
            rows = generate_rows(
                entity.fields,
                output.batch_size,
                fk_pools=build_lookup_pools(entity.lookup_attachments),
                rules=entity.rules,
                workflows=entity.workflows,
                trends=entity.trends,
                error_injections=entity.error_injections,
                event_triggers=entity.event_triggers,
                geo_routes=entity.geo_routes,
            )
            recorder.count(len(rows))
        return rows, output.events_per_second, output.plugin_name, output.config
    finally:
        db.close()


async def _deliver(fn, config: dict, rows: list[dict[str, Any]]) -> None:
    if inspect.iscoroutinefunction(fn):
        await fn(config, rows)
    else:
        await asyncio.to_thread(fn, config, rows)


async def _plugin_loop(output_id: UUID) -> None:
    failures = 0
    while True:
        try:
            result = await asyncio.to_thread(_load_output_sync, output_id)
            if result is None:
                return
            rows, events_per_second, plugin_name, config = result

            deliver = available_output_plugins().get(plugin_name)
            if deliver is None:
                logger.error(
                    "Output plugin '%s' is no longer installed; stopping producer %s",
                    plugin_name,
                    output_id,
                )
                return

            await _deliver(deliver, config, rows)
            metrics.record_delivery("plugin")
            failures = 0
            await asyncio.sleep(1 / events_per_second)
        except asyncio.CancelledError:
            raise
        except Exception:
            failures += 1
            metrics.record_delivery_error("plugin")
            logger.warning(
                "Plugin output producer %s failed (attempt %s/%s)",
                output_id,
                failures,
                MAX_CONSECUTIVE_FAILURES,
                exc_info=True,
            )
            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("Plugin output producer %s giving up", output_id)
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)


def start_plugin_output(output: PluginOutput) -> None:
    _tasks[output.id] = asyncio.create_task(_plugin_loop(output.id))


def stop_plugin_output(output_id: UUID) -> None:
    task = _tasks.pop(output_id, None)
    if task is not None:
        task.cancel()


async def stop_all_plugin_outputs() -> None:
    """Called on app shutdown so no task outlives the process."""
    tasks = list(_tasks.values())
    _tasks.clear()
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
