import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.continuity import RecordStatus, RecordStore, StoredRecord
from app.models.field import EntityField
from app.models.relationship import Relationship
from app.models.user import User
from app.schemas.continuity import (
    ApplyChangesRequest,
    ApplyChangesResponse,
    ChangeEventRead,
    GenerateIntoStoreRequest,
    GenerateIntoStoreResponse,
    RecordStoreCreate,
    RecordStoreRead,
    RecordStoreStats,
    StoredRecordRead,
)
from app.services import continuity

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/record-stores", tags=["record stores"]
)


def _get_store(store_id: uuid.UUID, entity_id: uuid.UUID, db: Session) -> RecordStore:
    store = db.get(RecordStore, store_id)
    if store is None or store.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record store not found")
    return store


def _counts(db: Session, store: RecordStore) -> tuple[int, int]:
    rows = db.execute(
        select(StoredRecord.status, func.count())
        .where(StoredRecord.store_id == store.id)
        .group_by(StoredRecord.status)
    ).all()
    by_status = {status_value: count for status_value, count in rows}
    return (
        by_status.get(RecordStatus.ACTIVE, 0),
        by_status.get(RecordStatus.DELETED, 0),
    )


def _parent_store_pools(db: Session, project_id: uuid.UUID, entity, store: RecordStore) -> dict:
    """Foreign-key pools drawn from parent entities' same-named stores.

    Matching by name rather than by a configured link keeps two independent
    populations independent: a "demo" order store draws from the "demo"
    customers, not from whichever customer store happened to be made first.
    """
    relationships = list(
        db.scalars(
            select(Relationship).where(
                Relationship.project_id == project_id,
                Relationship.source_entity_id == entity.id,
            )
        ).all()
    )
    stores_by_entity: dict[uuid.UUID, RecordStore] = {}
    for rel in relationships:
        parent = continuity.store_for(db, rel.target_entity_id, store.name)
        if parent is not None:
            stores_by_entity[rel.target_entity_id] = parent
    return continuity.pools_with_store(db, entity, stores_by_entity, relationships)


@router.get("", response_model=list[RecordStoreRead])
def list_record_stores(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecordStore]:
    _get_owned_entity(project_id, entity_id, current_user, db)
    return list(
        db.scalars(
            select(RecordStore)
            .where(RecordStore.entity_id == entity_id)
            .order_by(RecordStore.created_at)
        ).all()
    )


@router.post("", response_model=RecordStoreRead, status_code=status.HTTP_201_CREATED)
def create_record_store(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: RecordStoreCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordStore:
    _get_owned_entity(project_id, entity_id, current_user, db)

    field = db.get(EntityField, payload.identity_field_id)
    if field is None or field.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identity_field_id does not belong to this entity",
        )
    if field.nullable:
        # A nullable identity is not an identity. Refusing here beats
        # failing partway through the first generation call, when some
        # records are already stored.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nullable field cannot identify records — a null identity joins to nothing",
        )
    if db.scalar(
        select(RecordStore).where(
            RecordStore.entity_id == entity_id, RecordStore.name == payload.name
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This entity already has a record store with that name",
        )

    store = RecordStore(
        entity_id=entity_id,
        name=payload.name,
        identity_field_id=payload.identity_field_id,
        position=0,
        trend_state={},
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("/{store_id}", response_model=RecordStoreStats)
def get_record_store(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordStoreStats:
    _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)
    active, deleted = _counts(db, store)
    return RecordStoreStats(
        **RecordStoreRead.model_validate(store).model_dump(),
        active_records=active,
        deleted_records=deleted,
    )


@router.get("/{store_id}/records", response_model=list[StoredRecordRead])
def list_stored_records(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StoredRecord]:
    """Paged rather than "all of them": a store is a population, and a
    population is exactly the thing that grows without bound."""
    _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)
    return list(
        db.scalars(
            select(StoredRecord)
            .where(StoredRecord.store_id == store.id)
            .order_by(StoredRecord.sequence, StoredRecord.identity)
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.post("/{store_id}/generate", response_model=GenerateIntoStoreResponse)
def generate_into_store(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    payload: GenerateIntoStoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateIntoStoreResponse:
    """Add records to the store and return them.

    Foreign-key fields draw from a *parent store* when the parent entity has
    one with the same name, and fall back to the ordinary lookup pools
    otherwise. That is what makes the roadmap's sentence true: orders
    generated today reference customers generated last week, because the
    customers are still there to reference.
    """
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)

    pools = _parent_store_pools(db, project_id, entity, store)

    try:
        rows = continuity.generate_new(db, store, payload.count, fk_pools=pools)
    except continuity.ContinuityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    db.refresh(store)
    active, _ = _counts(db, store)
    return GenerateIntoStoreResponse(rows=rows, position=store.position, total_active=active)


@router.post("/{store_id}/changes", response_model=ApplyChangesResponse)
def apply_changes(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    payload: ApplyChangesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyChangesResponse:
    """Move the population forward one tick: some rows appear, some change,
    some go away — and every one of those is an event a CDC consumer can
    read back in order.

    This is what a real table looks like between two glances at it, and it
    is the thing a series of independent generation calls could never
    produce: without persistent identity, "the same row, changed" has no
    meaning.
    """
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)

    pools = _parent_store_pools(db, project_id, entity, store)

    try:
        events = continuity.apply_changes(
            db,
            store,
            inserts=payload.inserts,
            updates=payload.updates,
            deletes=payload.deletes,
            update_fields=payload.update_fields,
            fk_pools=pools,
        )
    except (continuity.ContinuityError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    read = [ChangeEventRead.model_validate(e) for e in events]
    db.commit()
    db.refresh(store)
    active, _ = _counts(db, store)
    return ApplyChangesResponse(
        events=read, next_sequence=store.change_sequence, total_active=active
    )


@router.get("/{store_id}/changes", response_model=list[ChangeEventRead])
def read_changes(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    after: int = Query(default=-1, ge=-1),
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Replay the change log from a cursor.

    `after` is exclusive, so a consumer passes back the last sequence it
    handled — the same contract as a Kafka offset. The default of -1 starts
    at the beginning.
    """
    _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)
    return continuity.read_changes(db, store, after=after, limit=limit)


@router.delete("/{store_id}/changes", status_code=status.HTTP_200_OK)
def trim_changes(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    before: int = Query(ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Drop events below `before`.

    Explicit rather than automatic: only the operator knows whether every
    consumer has caught up, and discarding events nobody has read turns a
    replayable stream into a lossy one.
    """
    _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)
    removed = continuity.delete_events_before(db, store, before)
    db.commit()
    return {"removed": removed}


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record_store(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    store_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    store = _get_store(store_id, entity_id, db)
    db.delete(store)
    db.commit()
