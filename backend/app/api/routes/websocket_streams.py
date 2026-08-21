import asyncio
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db import session as db_session
from app.db.session import get_db
from app.models.user import User
from app.models.websocket_stream import WebSocketStream
from app.schemas.websocket_stream import WebSocketStreamCreate, WebSocketStreamRead
from app.services.generator import build_lookup_pools, generate_rows

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/websocket-streams",
    tags=["websocket-streams"],
)

# No auth, no project/entity path segments, same reasoning as RestOutput's
# public_router — the token is the access control.
public_router = APIRouter(tags=["websocket-streams"])


@router.get("", response_model=list[WebSocketStreamRead])
def list_streams(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebSocketStream]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(WebSocketStream).filter(WebSocketStream.entity_id == entity.id).all()


@router.post("", response_model=WebSocketStreamRead, status_code=status.HTTP_201_CREATED)
def create_stream(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: WebSocketStreamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebSocketStream:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    stream = WebSocketStream(entity_id=entity_id, **payload.model_dump())
    db.add(stream)
    db.commit()
    db.refresh(stream)
    return stream


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stream(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    stream_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    stream = db.get(WebSocketStream, stream_id)
    if stream is None or stream.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    db.delete(stream)
    db.commit()


def _generate_batch_sync(token: str) -> tuple[list[dict], float] | None:
    """Runs entirely inside one thread with one short-lived session: look up
    the stream (re-checked every call so a delete takes effect on an
    already-open connection, not just new ones) and generate a batch. Returns
    plain data, not ORM objects, so nothing here can outlive the session and
    hit a DetachedInstanceError back in the async loop.

    Uses `db_session.SessionLocal()` (a module-attribute lookup) rather than
    importing `SessionLocal` by name — this endpoint isn't reached through
    FastAPI's `Depends(get_db)`, so tests can't override it the normal way;
    looking the factory up on the module each call lets conftest.py swap it
    for the duration of a test the same way it swaps the `get_db` dependency.
    """
    db = db_session.SessionLocal()
    try:
        stream = db.query(WebSocketStream).filter(WebSocketStream.token == token).first()
        if stream is None:
            return None
        entity = stream.entity
        rows = generate_rows(
            entity.fields,
            stream.batch_size,
            fk_pools=build_lookup_pools(entity.lookup_attachments),
            rules=entity.rules,
            workflows=entity.workflows,
            trends=entity.trends,
            error_injections=entity.error_injections,
            event_triggers=entity.event_triggers,
            geo_routes=entity.geo_routes,
        )
        return rows, stream.events_per_second
    finally:
        db.close()


@public_router.websocket("/public/stream/{token}")
async def stream_public(websocket: WebSocket, token: str) -> None:
    await websocket.accept()

    try:
        while True:
            try:
                result = await asyncio.to_thread(_generate_batch_sync, token)
            except ValueError as exc:
                await websocket.send_json({"error": str(exc)})
                await websocket.close(code=1011)
                return

            if result is None:
                await websocket.send_json({"error": "not found"})
                await websocket.close(code=4404)
                return

            rows, events_per_second = result
            await websocket.send_json(rows)
            await asyncio.sleep(1 / events_per_second)
    except WebSocketDisconnect:
        pass
