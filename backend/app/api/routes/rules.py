import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.rule import Rule
from app.models.user import User
from app.schemas.rule import RuleCreate, RuleRead
from app.services.expressions import ExpressionError, evaluate

router = APIRouter(prefix="/projects/{project_id}/entities/{entity_id}/rules", tags=["rules"])


@router.get("", response_model=list[RuleRead])
def list_rules(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Rule]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return entity.rules


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: RuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Rule:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)

    # Sanity-check the expression against dummy values for the entity's current
    # fields so an obviously broken/unsafe condition is rejected up front,
    # rather than surfacing only when someone tries to generate data.
    dummy_values = {field.name: 1 for field in entity.fields}
    try:
        evaluate(payload.condition, dummy_values)
    except ExpressionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    rule = Rule(entity_id=entity_id, condition=payload.condition)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    rule = db.get(Rule, rule_id)
    if rule is None or rule.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
