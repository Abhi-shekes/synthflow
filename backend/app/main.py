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
    kafka_outputs,
    lookup_attachments,
    lookup_tables,
    mqtt_outputs,
    outputs,
    projects,
    relationships,
    rest_outputs,
    rules,
    starter_templates,
    templates,
    timeline_replays,
    trends,
    websocket_streams,
    workflows,
)
from app.core.config import settings
from app.services.stream_producers import stop_all_producers


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Kafka/MQTT producers are in-process background tasks (see
    # app.services.stream_producers) — nothing else cancels them, so an
    # unclean shutdown would otherwise leak a task per active output.
    await stop_all_producers()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(entities.router, prefix=settings.API_V1_PREFIX)
app.include_router(generator_plugins.router, prefix=settings.API_V1_PREFIX)
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
app.include_router(outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(templates.router, prefix=settings.API_V1_PREFIX)
app.include_router(starter_templates.router, prefix=settings.API_V1_PREFIX)

# Deliberately outside /api/v1 and unauthenticated — see RestOutput's and
# WebSocketStream's docstrings.
app.include_router(rest_outputs.public_router)
app.include_router(websocket_streams.public_router)
app.include_router(timeline_replays.public_router)
