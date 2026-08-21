from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    database_connections,
    entities,
    health,
    outputs,
    projects,
    relationships,
    rest_outputs,
    rules,
    websocket_streams,
    workflows,
)
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

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
app.include_router(relationships.router, prefix=settings.API_V1_PREFIX)
app.include_router(rules.router, prefix=settings.API_V1_PREFIX)
app.include_router(workflows.router, prefix=settings.API_V1_PREFIX)
app.include_router(database_connections.router, prefix=settings.API_V1_PREFIX)
app.include_router(rest_outputs.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket_streams.router, prefix=settings.API_V1_PREFIX)
app.include_router(outputs.router, prefix=settings.API_V1_PREFIX)

# Deliberately outside /api/v1 and unauthenticated — see RestOutput's and
# WebSocketStream's docstrings.
app.include_router(rest_outputs.public_router)
app.include_router(websocket_streams.public_router)
