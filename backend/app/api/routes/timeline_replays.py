import asyncio
import uuid
from datetime import datetime

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
from app.api.routes.projects import _get_owned_project
from app.db import session as db_session
from app.db.session import get_db
from app.models.lookup_table import LookupTable
from app.models.timeline_replay import TimelineReplay
from app.models.user import User
from app.schemas.timeline_replay import TimelineReplayCreate, TimelineReplayRead
from app.services.timeline_replay import (
    TimelineReplayError,
    build_schedule,
    parse_timestamp,
    validate_timestamp_column,
)

router = APIRouter(prefix="/projects/{project_id}/timeline-replays", tags=["timeline-replays"])

# No auth, no project path segment — same trust model as RestOutput's and
# WebSocketStream's public routers: the token is the access control.
public_router = APIRouter(tags=["timeline-replays"])

MIN_TICK_DELAY_SECONDS = 0.0
MAX_TICK_DELAY_SECONDS = 30.0


@router.get("", response_model=list[TimelineReplayRead])
def list_timeline_replays(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TimelineReplay]:
    _get_owned_project(project_id, current_user, db)
    return (
        db.query(TimelineReplay)
        .filter(TimelineReplay.project_id == project_id)
        .order_by(TimelineReplay.created_at)
        .all()
    )


@router.post("", response_model=TimelineReplayRead, status_code=status.HTTP_201_CREATED)
def create_timeline_replay(
    project_id: uuid.UUID,
    payload: TimelineReplayCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimelineReplay:
    _get_owned_project(project_id, current_user, db)

    lookup_table = db.get(LookupTable, payload.lookup_table_id)
    if lookup_table is None or lookup_table.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lookup_table_id does not belong to this project",
        )
    if payload.timestamp_column not in lookup_table.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{payload.timestamp_column}' is not a column of this lookup table",
        )

    try:
        validate_timestamp_column(lookup_table.data, payload.timestamp_column)
    except TimelineReplayError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    replay = TimelineReplay(project_id=project_id, **payload.model_dump())
    db.add(replay)
    db.commit()
    db.refresh(replay)
    return replay


@router.delete("/{replay_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timeline_replay(
    project_id: uuid.UUID,
    replay_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    replay = db.get(TimelineReplay, replay_id)
    if replay is None or replay.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Timeline replay not found"
        )
    db.delete(replay)
    db.commit()


def _load_schedule_sync(token: str) -> tuple[list[dict], str, float] | None:
    """One short-lived session, plain data out (not ORM objects) so nothing
    outlives the session — same reasoning as
    websocket_streams._generate_batch_sync, including looking up
    `db_session.SessionLocal` fresh each call so tests can override it.
    Unlike that function, this runs once per connection, not once per tick
    — see TimelineReplay's docstring for why."""
    db = db_session.SessionLocal()
    try:
        replay = db.query(TimelineReplay).filter(TimelineReplay.token == token).first()
        if replay is None:
            return None
        schedule = build_schedule(replay.lookup_table.data, replay.timestamp_column)
        return schedule, replay.timestamp_column, replay.speed_multiplier
    finally:
        db.close()


@public_router.websocket("/public/replay/{token}")
async def replay_public(websocket: WebSocket, token: str) -> None:
    await websocket.accept()

    try:
        result = await asyncio.to_thread(_load_schedule_sync, token)
        if result is None:
            await websocket.send_json({"error": "not found"})
            await websocket.close(code=4404)
            return

        schedule, column, speed_multiplier = result
        previous_ts: datetime | None = None
        while True:
            for row in schedule:
                current_ts = parse_timestamp(row[column])
                if previous_ts is not None:
                    delay = (current_ts - previous_ts).total_seconds() / speed_multiplier
                    # Also clamps the negative delay from wrapping back to
                    # the first row after the last — an instant restart,
                    # not a special case.
                    delay = min(max(delay, MIN_TICK_DELAY_SECONDS), MAX_TICK_DELAY_SECONDS)
                    await asyncio.sleep(delay)
                await websocket.send_json(row)
                previous_ts = current_ts
    except WebSocketDisconnect:
        pass
