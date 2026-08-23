import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.db.session import get_db
from app.models.database_connection import DatabaseConnection
from app.models.entity import Entity
from app.models.kafka_output import KafkaOutput
from app.models.mqtt_output import MQTTOutput
from app.models.plugin_output import PluginOutput
from app.models.rabbitmq_output import RabbitMQOutput
from app.models.rest_output import RestOutput
from app.models.timeline_replay import TimelineReplay
from app.models.user import User
from app.models.webhook_output import WebhookOutput
from app.models.websocket_stream import WebSocketStream

router = APIRouter(prefix="/projects/{project_id}/outputs", tags=["outputs"])


class OutputSummary(BaseModel):
    type: Literal[
        "database",
        "rest",
        "websocket",
        "timeline_replay",
        "kafka",
        "mqtt",
        "rabbitmq",
        "webhook",
        "plugin",
    ]
    id: uuid.UUID
    detail: str


@router.get("", response_model=list[OutputSummary])
def list_outputs(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OutputSummary]:
    """A read-only aggregate over every output configured for this project,
    across the separate typed tables that back each output kind (not one
    polymorphic table: outputs
    have genuinely different shapes, and separate typed tables match how
    Relationship/Rule/Workflow already work in this codebase). This IS the
    plugin manager for now — an output is "enabled" by creating a row in its
    own table and "disabled" by deleting it; this endpoint is just a unified
    view over what already exists, not a new persisted concept."""
    _get_owned_project(project_id, current_user, db)

    summaries: list[OutputSummary] = []

    connections = (
        db.query(DatabaseConnection).filter(DatabaseConnection.project_id == project_id).all()
    )
    for conn in connections:
        summaries.append(
            OutputSummary(
                type="database",
                id=conn.id,
                detail=f"{conn.name} ({conn.dialect}) {conn.host}:{conn.port}/{conn.database}",
            )
        )

    rest_outputs = (
        db.query(RestOutput)
        .join(Entity, RestOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in rest_outputs:
        summaries.append(
            OutputSummary(
                type="rest",
                id=output.id,
                detail=f"{output.entity.name}: /public/rest/{output.token}",
            )
        )

    streams = (
        db.query(WebSocketStream)
        .join(Entity, WebSocketStream.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for stream in streams:
        summaries.append(
            OutputSummary(
                type="websocket",
                id=stream.id,
                detail=f"{stream.entity.name}: /public/stream/{stream.token}",
            )
        )

    replays = db.query(TimelineReplay).filter(TimelineReplay.project_id == project_id).all()
    for replay in replays:
        summaries.append(
            OutputSummary(
                type="timeline_replay",
                id=replay.id,
                detail=f"{replay.lookup_table.name}: /public/replay/{replay.token}",
            )
        )

    kafka_outputs = (
        db.query(KafkaOutput)
        .join(Entity, KafkaOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in kafka_outputs:
        summaries.append(
            OutputSummary(
                type="kafka",
                id=output.id,
                detail=f"{output.entity.name}: {output.bootstrap_servers}/{output.topic}",
            )
        )

    mqtt_outputs = (
        db.query(MQTTOutput)
        .join(Entity, MQTTOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in mqtt_outputs:
        broker = f"{output.broker_host}:{output.broker_port}"
        summaries.append(
            OutputSummary(
                type="mqtt",
                id=output.id,
                detail=f"{output.entity.name}: {broker}/{output.topic}",
            )
        )

    rabbitmq_outputs = (
        db.query(RabbitMQOutput)
        .join(Entity, RabbitMQOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in rabbitmq_outputs:
        broker = f"{output.host}:{output.port}"
        # An empty exchange is RabbitMQ's default one, where the routing
        # key is the queue name — say so rather than showing a blank.
        exchange = output.exchange or "(default)"
        summaries.append(
            OutputSummary(
                type="rabbitmq",
                id=output.id,
                detail=f"{output.entity.name}: {broker} {exchange} -> {output.routing_key}",
            )
        )

    webhook_outputs = (
        db.query(WebhookOutput)
        .join(Entity, WebhookOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in webhook_outputs:
        summaries.append(
            OutputSummary(
                type="webhook",
                id=output.id,
                detail=f"{output.entity.name}: POST {output.url}",
            )
        )

    plugin_outputs = (
        db.query(PluginOutput)
        .join(Entity, PluginOutput.entity_id == Entity.id)
        .filter(Entity.project_id == project_id)
        .all()
    )
    for output in plugin_outputs:
        summaries.append(
            OutputSummary(
                type="plugin",
                id=output.id,
                detail=f"{output.entity.name}: {output.plugin_name}",
            )
        )

    return summaries
