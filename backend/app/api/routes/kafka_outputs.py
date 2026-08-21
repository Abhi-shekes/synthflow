import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.kafka_output import KafkaOutput
from app.models.user import User
from app.schemas.kafka_output import KafkaOutputCreate, KafkaOutputRead
from app.services import install
from app.services.stream_producers import start_kafka_producer, stop_producer

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/kafka-outputs", tags=["kafka-outputs"]
)


@router.get("", response_model=list[KafkaOutputRead])
def list_kafka_outputs(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KafkaOutput]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(KafkaOutput).filter(KafkaOutput.entity_id == entity.id).all()


@router.post("", response_model=KafkaOutputRead, status_code=status.HTTP_201_CREATED)
async def create_kafka_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: KafkaOutputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KafkaOutput:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    try:
        install.require("kafka")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    output = KafkaOutput(entity_id=entity_id, **payload.model_dump())
    db.add(output)
    db.commit()
    db.refresh(output)
    start_kafka_producer(output)
    return output


@router.delete("/{kafka_output_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kafka_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    kafka_output_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    output = db.get(KafkaOutput, kafka_output_id)
    if output is None or output.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kafka output not found")
    stop_producer(output.id)
    db.delete(output)
    db.commit()
