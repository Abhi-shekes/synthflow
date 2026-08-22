import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    api_keys,
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
    object_storage,
    organizations,
    output_plugins,
    outputs,
    plugin_outputs,
    profiling,
    projects,
    rabbitmq_outputs,
    record_stores,
    relationships,
    rest_outputs,
    rule_functions,
    rules,
    schema_import,
    starter_templates,
    templates,
    timeline_replays,
    trends,
    webhook_outputs,
    websocket_streams,
    workflows,
)
from app.api.routes import (
    audit as audit_routes,
)
from app.core.config import settings
from app.db import session as db_session
from app.services import access, audit
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


@app.middleware("http")
async def audit_mutations(request: Request, call_next):
    """Record every mutating request that reached an authenticated route.

    Middleware rather than calls inside the routes, because an audit log
    assembled by remembering to log is an audit log with holes in it — and
    the holes are invisible, since a missing entry looks exactly like a thing
    that never happened. A route added tomorrow is covered without anyone
    thinking about it.

    Failures are recorded too. A 403 is precisely the kind of event an audit
    log exists to show, and keeping only successes would hide the attempts.

    A failure to *write* the entry is swallowed, deliberately: an audit log
    that can take the API down with it is a worse trade than a log with a
    gap, and the gap is already visible in the application's own error log.
    """
    # Set *before* `call_next`, and here rather than in a dependency. A
    # context variable propagates down into tasks spawned from this context
    # but never back up out of one, and FastAPI runs a sync dependency in a
    # worker thread with its own copy of the context — so setting it in
    # `get_current_user` left the route handler, running in a *different*
    # copy, still seeing the default. Which meant `access.may` read every
    # request as a GET and a viewer could write.
    access.current_method.set(request.method)

    response = await call_next(request)

    if not settings.AUDIT_LOG or request.method not in audit.MUTATING_METHODS:
        return response
    actor = getattr(request.state, "actor", None)
    if actor is None:
        # Unauthenticated, or a route with no auth dependency. There is no
        # "who", so there is nothing an audit entry could usefully say.
        return response

    route = request.scope.get("route")
    try:
        # Looked up on the module rather than imported by name, so the
        # test suite's swap of `db_session.SessionLocal` reaches it. An
        # imported name would have been bound at import time and kept
        # pointing at the production database — the same reason the
        # websocket stream loop resolves it this way.
        with db_session.SessionLocal() as db:
            audit.record(
                db,
                user_id=actor["user_id"],
                actor_email=actor["actor_email"],
                actor_kind=actor["actor_kind"],
                api_key_prefix=actor["api_key_prefix"],
                method=request.method,
                route=getattr(route, "path", request.url.path),
                status_code=response.status_code,
                path_params=request.scope.get("path_params") or {},
            )
            db.commit()
    except Exception:
        logger.exception("Could not write an audit entry for %s %s", request.method, request.url)

    return response


app.include_router(health.router)
# Outside /api/v1 and unauthenticated, like /healthz — see its docstring.
app.include_router(metrics.router)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(api_keys.router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(organizations.router, prefix=settings.API_V1_PREFIX)
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
app.include_router(record_stores.router, prefix=settings.API_V1_PREFIX)
app.include_router(error_injections.router, prefix=settings.API_V1_PREFIX)
app.include_router(lookup_tables.router, prefix=settings.API_V1_PREFIX)
app.include_router(lookup_attachments.router, prefix=settings.API_V1_PREFIX)
app.include_router(geo_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(database_connections.router, prefix=settings.API_V1_PREFIX)
app.include_router(object_storage.router, prefix=settings.API_V1_PREFIX)
app.include_router(rabbitmq_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(webhook_outputs.router, prefix=settings.API_V1_PREFIX)
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
app.include_router(profiling.router, prefix=settings.API_V1_PREFIX)

# Deliberately outside /api/v1 and unauthenticated — see RestOutput's and
# WebSocketStream's docstrings.
app.include_router(rest_outputs.public_router)
app.include_router(websocket_streams.public_router)
app.include_router(timeline_replays.public_router)
