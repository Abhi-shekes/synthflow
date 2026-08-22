"""Generation that remembers what it generated last time.

Every call to the engine before Phase 13 produced an independent universe.
Ask for 100 customers twice and you get 200 strangers; a trend replays from
its start on every batch; a vehicle drives to the end of its route and stops
there. That is right for seeding a database once and wrong for anything
watching a system *change* — a CDC pipeline, an ETL feed, a dashboard.

A `RecordStore` is the missing piece: a population that survives between
calls, plus the cursor the position-based features (trends, geo routes)
always needed and never had.

Two operations, deliberately separate:

* `generate_new` adds records to a store. The customers exist afterwards.
* `identity_pool` hands a child entity the identity values of a parent's
  *stored* records, so today's orders reference yesterday's customers
  instead of a parent batch invented moments ago.

Together those are the roadmap's sentence in code: "a customer generated
yesterday still exists today and can receive new orders."

The store is the *population*, never the output log. Emitting a million rows
does not write a million rows here — see `RecordStore`'s docstring for why
that boundary matters.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.continuity import RecordStatus, RecordStore, StoredRecord
from app.models.entity import Entity
from app.services.generator import build_lookup_pools, iter_rows


class ContinuityError(ValueError):
    pass


def _identity_of(row: dict[str, Any], field_name: str) -> str:
    """A record's key, as text.

    Stringified because the column holds identities from every field type
    and is only ever compared for equality. `None` is refused rather than
    stored: a record whose identity is null is a record nothing downstream
    can join to, and silently keeping it would push the failure to whoever
    consumes the stream.
    """
    value = row.get(field_name)
    if value is None:
        raise ContinuityError(
            f"Field '{field_name}' identifies records in this store but generated null"
        )
    return str(value)


def identity_pool(db: Session, store: RecordStore) -> list[Any]:
    """The identity values of a store's live records.

    This is what makes a relationship span time. `generate_project` builds a
    child's foreign-key pool from a parent batch it just generated; passing
    this instead points the child at the parent's *persisted* population, so
    an order generated today can belong to a customer generated last week.

    Deleted records are excluded: a tombstone exists so a consumer can be
    told the record went away, not so new children can be attached to it.
    """
    rows = db.scalars(
        select(StoredRecord.data)
        .where(StoredRecord.store_id == store.id)
        .where(StoredRecord.status == RecordStatus.ACTIVE)
    ).all()
    field_name = store.identity_field.name
    return [row[field_name] for row in rows if field_name in row]


def existing_identities(db: Session, store: RecordStore) -> set[str]:
    """Every identity the store has ever held, tombstones included.

    Used to keep a new record from reusing a deleted record's key. Recycling
    one would make a delete followed by an insert indistinguishable from an
    update to a consumer replaying the stream, which is exactly the
    distinction Phase 13 exists to preserve.
    """
    return set(
        db.scalars(select(StoredRecord.identity).where(StoredRecord.store_id == store.id)).all()
    )


def generate_new(
    db: Session,
    store: RecordStore,
    count: int,
    fk_pools: dict[str, list[Any]] | None = None,
    max_attempts_factor: int = 5,
) -> list[dict[str, Any]]:
    """Generate `count` new records, persist them, and advance the cursor.

    The rows come back so a caller can write them somewhere as well — a
    store records that a customer exists, it does not replace the output.

    Trends and geo routes continue from `store.position` rather than
    restarting at 0, and `store.trend_state` carries a `random_walk`'s
    running value across the call boundary. Both are written back before
    returning, so the next call picks up exactly where this one stopped.

    **Identity collisions are retried, not tolerated.** The engine has no
    idea a store exists, so nothing stops it generating an identity that is
    already taken — likely for a small enum-ish key, rare for a UUID. A
    collision is skipped and another row generated, bounded by
    `max_attempts_factor * count` so an identity field with a tiny value
    space fails loudly instead of looping forever.
    """
    if count <= 0:
        return []

    entity: Entity = store.entity
    identity_name = store.identity_field.name
    if not any(f.name == identity_name for f in entity.fields):
        raise ContinuityError(f"Field '{identity_name}' is no longer on entity '{entity.name}'")

    taken = existing_identities(db, store)
    trend_state = dict(store.trend_state or {})
    position = store.position

    kept: list[dict[str, Any]] = []
    attempts = 0
    limit = max(max_attempts_factor * count, count + 10)
    while len(kept) < count and attempts < limit:
        wanted = count - len(kept)
        for row in iter_rows(
            entity.fields,
            wanted,
            fk_pools=fk_pools,
            rules=entity.rules,
            workflows=entity.workflows,
            trends=entity.trends,
            error_injections=entity.error_injections,
            event_triggers=entity.event_triggers,
            geo_routes=entity.geo_routes,
            start_position=position,
            trend_state=trend_state,
        ):
            attempts += 1
            position += 1
            identity = _identity_of(row, identity_name)
            if identity in taken:
                continue
            taken.add(identity)
            kept.append(row)
            db.add(
                StoredRecord(
                    store_id=store.id,
                    identity=identity,
                    data=row,
                    # `position` has already been advanced past this row, so
                    # the sequence is the position it occupied.
                    sequence=position - 1,
                    version=1,
                    status=RecordStatus.ACTIVE,
                )
            )
            if len(kept) == count:
                break

    if len(kept) < count:
        raise ContinuityError(
            f"Only {len(kept)} of {count} records had an identity not already in this "
            f"store — '{identity_name}' may not have enough distinct values to keep "
            "generating new records"
        )

    store.position = position
    store.trend_state = trend_state
    db.flush()
    return kept


def store_for(db: Session, entity_id: uuid.UUID, name: str) -> RecordStore | None:
    return db.scalar(
        select(RecordStore).where(RecordStore.entity_id == entity_id, RecordStore.name == name)
    )


def pools_with_store(
    db: Session,
    entity: Entity,
    stores_by_entity: dict[uuid.UUID, RecordStore],
    relationships: list[Any],
) -> dict[str, list[Any]]:
    """Foreign-key pools for `entity`, drawn from parents' stores.

    The lookup-table pools come first and a relationship pool overrides
    them, matching `generate_project`'s existing precedence so a field
    covered by both behaves the same whether or not a store is involved.
    """
    pools = build_lookup_pools(entity.lookup_attachments)
    fields_by_id = {f.id: f for f in entity.fields}
    for rel in relationships:
        if rel.source_entity_id != entity.id:
            continue
        parent_store = stores_by_entity.get(rel.target_entity_id)
        if parent_store is None:
            continue
        source_field = fields_by_id.get(rel.source_field_id)
        if source_field is None:
            continue
        values = identity_pool(db, parent_store)
        if values:
            pools[source_field.name] = values
    return pools
