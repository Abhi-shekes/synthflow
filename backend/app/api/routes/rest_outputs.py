import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.core.config import settings
from app.db.session import get_db
from app.models.rest_output import RestOutput
from app.models.user import User
from app.schemas.rest_output import RestOutputCreate, RestOutputRead
from app.services.generator import build_lookup_pools, generate_rows

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/rest-outputs", tags=["rest-outputs"]
)

# No auth, no project/entity path segments — the token alone is the access
# control (see app.models.rest_output.RestOutput), so this deliberately isn't
# nested under /api/v1 or the entity's own URL.
public_router = APIRouter(prefix="/public/rest", tags=["rest-outputs"])


@router.get("", response_model=list[RestOutputRead])
def list_rest_outputs(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RestOutput]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(RestOutput).filter(RestOutput.entity_id == entity.id).all()


@router.post("", response_model=RestOutputRead, status_code=status.HTTP_201_CREATED)
def create_rest_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: RestOutputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RestOutput:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity has no fields to generate",
        )
    output = RestOutput(entity_id=entity_id, default_count=payload.default_count)
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


@router.delete("/{output_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rest_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    output_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    output = db.get(RestOutput, output_id)
    if output is None or output.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="REST output not found")
    db.delete(output)
    db.commit()


@public_router.get("/{token}")
def fetch_public_rest_output(
    token: str,
    count: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    output = db.query(RestOutput).filter(RestOutput.token == token).first()
    if output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    entity = output.entity
    resolved_count = count if count is not None else output.default_count
    if resolved_count < 1 or resolved_count > settings.MAX_GENERATE_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"count must be between 1 and {settings.MAX_GENERATE_ROWS}",
        )

    try:
        return generate_rows(
            entity.fields,
            resolved_count,
            fk_pools=build_lookup_pools(entity.lookup_attachments),
            rules=entity.rules,
            workflows=entity.workflows,
            trends=entity.trends,
            error_injections=entity.error_injections,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
