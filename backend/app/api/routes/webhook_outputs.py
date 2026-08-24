import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.core.network import UnsafeHostError, ensure_not_internal_service
from app.db.session import get_db
from app.models.user import User
from app.models.webhook_output import WebhookOutput
from app.schemas.webhook_output import WebhookOutputCreate, WebhookOutputRead
from app.services.stream_producers import start_webhook_producer, stop_producer

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/webhook-outputs", tags=["webhook-outputs"]
)


@router.get("", response_model=list[WebhookOutputRead])
def list_webhook_outputs(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebhookOutput]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(WebhookOutput).filter(WebhookOutput.entity_id == entity.id).all()


@router.post("", response_model=WebhookOutputRead, status_code=status.HTTP_201_CREATED)
async def create_webhook_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: WebhookOutputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebhookOutput:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )

    parsed = urlparse(payload.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only http and https URLs are supported, not '{parsed.scheme}'",
        )
    if not parsed.hostname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That URL has no host")
    try:
        # Only loopback/link-local are refused, not RFC1918 — a webhook to
        # an internal service is a legitimate, common target. See
        # app.core.network's module docstring.
        ensure_not_internal_service(parsed.hostname)
    except UnsafeHostError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # No optional extra: urllib and hmac are stdlib, so a signed webhook
    # works in the smallest possible install.
    output = WebhookOutput(entity_id=entity_id, **payload.model_dump())
    db.add(output)
    db.commit()
    db.refresh(output)
    start_webhook_producer(output)
    return output


@router.delete("/{webhook_output_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    webhook_output_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    output = db.get(WebhookOutput, webhook_output_id)
    if output is None or output.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook output not found"
        )
    stop_producer(output.id)
    db.delete(output)
    db.commit()
