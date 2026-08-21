import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    database_connections,
    entities,
    error_injections,
    event_triggers,
    generator_plugins,
    geo_routes,
    health,
    install_config,
    jobs,
    kafka_outputs,
    lookup_attachments,
    lookup_tables,
    metrics,
    mqtt_outputs,
    output_plugins,
    outputs,
    plugin_outputs,
    projects,
    relationships,
    rest_outputs,
    rule_functions,
    rules,
    schema_import,
    starter_templates,
    templates,
    timeline_replays,
    trends,
    websocket_streams,
    workflows,
)
from app.core.config import settings
from app.services.jobs import resume_producers, startup_recovery, worker_pass
from app.services.metrics import init_gauges
from app.services.plugin_output_producers import stop_all_plugin_outputs
from app.services.stream_producers import stop_all_producers

logger = logging.getLogger(__name__)


async def _worker_loop() -> None:
    """The in-process job worker.

    Runs alongside the API rather than as a separate process: the queue
    lives in the database (see app.services.jobs), so an extra container
    would buy distribution we don't need at this scale while costing a
    whole second deployment shape. Multiple API replicas can each run
    this safely — Postgres' SKIP LOCKED hands each of them different
    jobs.

    Blocking work goes through asyncio.to_thread so a large job can't
    stall the event loop serving requests.
    """
    while True:
        try:
            did_work = await asyncio.to_thread(worker_pass)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the loop must outlive any one failure
            logger.warning("Worker loop error", exc_info=True)
            did_work = False
        # Poll again immediately while there's a backlog; idle otherwise.
        if not did_work:
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Point the "active producers" gauges at the live task registries
    # (see app.services.metrics) — done at startup rather than import
    # time so the callbacks aren't wired up during test collection.
    init_gauges()

    worker: asyncio.Task | None = None
    if settings.RUN_WORKER:
        # Put interrupted work back on the queue and restart the
        # background producers a previous process owned. This is what
        # finally makes "survives a restart" true for Kafka/MQTT/plugin
        # outputs, which have documented that gap since they were built.
        try:
            recovered = await asyncio.to_thread(startup_recovery)
            if any(recovered.values()):
                logger.info("Startup recovery: %s", recovered)
            # Not to_thread: this creates asyncio tasks, which must
            # happen on the event loop.
            await resume_producers()
        except Exception:  # noqa: BLE001 - never block boot on recovery
            logger.warning("Startup recovery failed", exc_info=True)

        worker = asyncio.create_task(_worker_loop())

    yield

    if worker is not None:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
    # Kafka/MQTT/plugin-output producers are in-process background tasks
    # (see app.services.stream_producers and
    # app.services.plugin_output_producers) — nothing else cancels them,
    # so an unclean shutdown would otherwise leak a task per active output.
    await stop_all_producers()
    await stop_all_plugin_outputs()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
# Outside /api/v1 and unauthenticated, like /healthz — see its docstring.
app.include_router(metrics.router)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(entities.router, prefix=settings.API_V1_PREFIX)
app.include_router(generator_plugins.router, prefix=settings.API_V1_PREFIX)
app.include_router(install_config.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(rule_functions.router, prefix=settings.API_V1_PREFIX)
app.include_router(relationships.router, prefix=settings.API_V1_PREFIX)
app.include_router(rules.router, prefix=settings.API_V1_PREFIX)
app.include_router(event_triggers.router, prefix=settings.API_V1_PREFIX)
app.include_router(workflows.router, prefix=settings.API_V1_PREFIX)
app.include_router(trends.router, prefix=settings.API_V1_PREFIX)
app.include_router(error_injections.router, prefix=settings.API_V1_PREFIX)
app.include_router(lookup_tables.router, prefix=settings.API_V1_PREFIX)
app.include_router(lookup_attachments.router, prefix=settings.API_V1_PREFIX)
app.include_router(geo_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(database_connections.router, prefix=settings.API_V1_PREFIX)
app.include_router(rest_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket_streams.router, prefix=settings.API_V1_PREFIX)
app.include_router(timeline_replays.router, prefix=settings.API_V1_PREFIX)
app.include_router(kafka_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(mqtt_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(plugin_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(output_plugins.router, prefix=settings.API_V1_PREFIX)
app.include_router(outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(templates.router, prefix=settings.API_V1_PREFIX)
app.include_router(starter_templates.router, prefix=settings.API_V1_PREFIX)
app.include_router(schema_import.router, prefix=settings.API_V1_PREFIX)

# Deliberately outside /api/v1 and unauthenticated — see RestOutput's and
# WebSocketStream's docstrings.
app.include_router(rest_outputs.public_router)
app.include_router(websocket_streams.public_router)
app.include_router(timeline_replays.public_router)
