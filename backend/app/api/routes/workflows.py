import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.field import EntityField
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowRead

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/workflows", tags=["workflows"]
)


@router.get("", response_model=list[WorkflowRead])
def list_workflows(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Workflow]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.workflows


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workflow:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_id does not belong to this entity",
        )
    if any(w.field_id == payload.field_id for w in entity.workflows):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This field already has a workflow attached",
        )

    states = set(payload.states)
    if not states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="states cannot be empty"
        )
    if not payload.initial_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="initial_states cannot be empty"
        )
    if not set(payload.initial_states) <= states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="initial_states must be a subset of states",
        )
    for t in payload.transitions:
        if t.source not in states or t.target not in states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transition {t.source} -> {t.target} references a state not in states",
            )
    if payload.stop_probabilities:
        if not set(payload.stop_probabilities) <= states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stop_probabilities keys must be states",
            )
        if any(not (0 <= p <= 1) for p in payload.stop_probabilities.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stop_probabilities values must be between 0 and 1",
            )

    workflow = Workflow(
        entity_id=entity_id,
        field_id=payload.field_id,
        states=payload.states,
        initial_states=payload.initial_states,
        transitions=[t.model_dump() for t in payload.transitions],
        stop_probabilities=payload.stop_probabilities,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    db.delete(workflow)
    db.commit()
