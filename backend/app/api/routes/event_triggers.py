import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity, dummy_row_values
from app.db.session import get_db
from app.models.event_trigger import EventTrigger
from app.models.user import User
from app.schemas.event_trigger import EventTriggerCreate, EventTriggerRead
from app.services.expressions import ExpressionError, evaluate

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/event-triggers", tags=["event-triggers"]
)


@router.get("", response_model=list[EventTriggerRead])
def list_event_triggers(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EventTrigger]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.event_triggers


@router.post("", response_model=EventTriggerRead, status_code=status.HTTP_201_CREATED)
def create_event_trigger(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: EventTriggerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventTrigger:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    # Same sanity-check as Rule: evaluate against dummy values for the
    # entity's own fields plus a dummy row per related entity (see
    # dummy_row_values) so an obviously broken/unsafe condition is rejected
    # up front, rather than surfacing only when someone generates.
    try:
        evaluate(payload.condition, dummy_row_values(entity, db))
    except ExpressionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    event_trigger = EventTrigger(
        entity_id=entity_id, label=payload.label, condition=payload.condition
    )
    db.add(event_trigger)
    db.commit()
    db.refresh(event_trigger)
    return event_trigger


@router.delete("/{event_trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_trigger(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    event_trigger_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    event_trigger = db.get(EventTrigger, event_trigger_id)
    if event_trigger is None or event_trigger.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event trigger not found")
    db.delete(event_trigger)
    db.commit()
