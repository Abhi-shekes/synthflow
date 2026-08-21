import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.mqtt_output import MQTTOutput
from app.models.user import User
from app.schemas.mqtt_output import MQTTOutputCreate, MQTTOutputRead
from app.services import install
from app.services.stream_producers import start_mqtt_producer, stop_producer

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/mqtt-outputs", tags=["mqtt-outputs"]
)


@router.get("", response_model=list[MQTTOutputRead])
def list_mqtt_outputs(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MQTTOutput]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(MQTTOutput).filter(MQTTOutput.entity_id == entity.id).all()


@router.post("", response_model=MQTTOutputRead, status_code=status.HTTP_201_CREATED)
async def create_mqtt_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: MQTTOutputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MQTTOutput:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    try:
        install.require("mqtt")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    output = MQTTOutput(entity_id=entity_id, **payload.model_dump())
    db.add(output)
    db.commit()
    db.refresh(output)
    start_mqtt_producer(output)
    return output


@router.delete("/{mqtt_output_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mqtt_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    mqtt_output_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    output = db.get(MQTTOutput, mqtt_output_id)
    if output is None or output.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MQTT output not found")
    stop_producer(output.id)
    db.delete(output)
    db.commit()
