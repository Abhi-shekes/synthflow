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

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.continuity import (
    ChangeEvent,
    ChangeOperation,
    RecordStatus,
    RecordStore,
    RecordVersion,
    SCDType,
    StoredRecord,
)
from app.models.entity import Entity
from app.services.generator import advance_state, build_lookup_pools, iter_rows


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
    event_time: datetime | None = None,
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

    at = event_time or datetime.now(UTC)
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
            _log(
                db,
                store,
                ChangeOperation.INSERT,
                identity,
                before=None,
                after=row,
                version=1,
                event_time=at,
            )
            _open_version(db, store, identity, 1, row, at)
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


# --------------------------------------------------------------------------
# Change data capture
# --------------------------------------------------------------------------


def _log(
    db: Session,
    store: RecordStore,
    operation: ChangeOperation,
    identity: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    version: int,
    event_time: datetime,
) -> ChangeEvent:
    """Append one event and advance the store's change cursor.

    The cursor lives on the store rather than being derived with
    `max(sequence) + 1`, so two concurrent calls cannot compute the same
    next value — the unique constraint would catch it, but only by failing
    a request that had no reason to fail.
    """
    event = ChangeEvent(
        store_id=store.id,
        sequence=store.change_sequence,
        operation=operation,
        identity=identity,
        before=before,
        after=after,
        version=version,
        event_time=event_time,
    )
    store.change_sequence += 1
    db.add(event)
    return event


def _open_version(
    db: Session,
    store: RecordStore,
    identity: str,
    version: int,
    data: dict[str, Any],
    valid_from: datetime,
) -> None:
    """Start a new SCD type 2 version. No-op for a type 1 store."""
    if store.scd_type != SCDType.TYPE_2:
        return
    db.add(
        RecordVersion(
            store_id=store.id,
            identity=identity,
            version=version,
            data=data,
            valid_from=valid_from,
            valid_to=None,
        )
    )


def _close_version(db: Session, store: RecordStore, identity: str, valid_to: datetime) -> None:
    """Close whichever version is currently open. No-op for type 1.

    Closes by `valid_to IS NULL` rather than by version number: that is the
    single place "current" is recorded, so it cannot disagree with anything
    else.
    """
    if store.scd_type != SCDType.TYPE_2:
        return
    current = db.scalar(
        select(RecordVersion)
        .where(RecordVersion.store_id == store.id)
        .where(RecordVersion.identity == identity)
        .where(RecordVersion.valid_to.is_(None))
    )
    if current is not None:
        current.valid_to = valid_to


def _active_records(db: Session, store: RecordStore) -> list[StoredRecord]:
    return list(
        db.scalars(
            select(StoredRecord)
            .where(StoredRecord.store_id == store.id)
            .where(StoredRecord.status == RecordStatus.ACTIVE)
        ).all()
    )


def _updated_row(
    store: RecordStore,
    record: StoredRecord,
    fields_to_change: list[str],
) -> dict[str, Any]:
    """The record's next values.

    Three kinds of field behave differently, and the differences are the
    point rather than special cases:

    * A **workflow** field advances one step from where this record already
      is (see `generator.advance_state`). Re-randomising it would send a
      customer who reached checkout back to signed-up, which is the exact
      reset Phase 13 exists to close.
    * A **trend** field continues from the store's cursor, so a value that
      has been climbing keeps climbing.
    * Everything else is regenerated independently.

    The identity field is never touched. Changing it would not be an update
    at all — it would be a delete and an unrelated insert wearing one
    event's clothing.
    """
    entity: Entity = store.entity
    identity_name = store.identity_field.name
    workflows_by_field = {w.field.name: w for w in entity.workflows}
    trends_by_field = {t.field.name: t for t in entity.trends}
    fields_by_name = {f.name: f for f in entity.fields}

    row = dict(record.data)
    for name in fields_to_change:
        if name == identity_name or name not in fields_by_name:
            continue
        if name in workflows_by_field:
            current = row.get(name)
            row[name] = advance_state(workflows_by_field[name], str(current))
            continue
        if name in trends_by_field:
            # One row at the store's current position, so the series
            # continues rather than jumping.
            [generated] = list(
                iter_rows(
                    [fields_by_name[name]],
                    1,
                    trends=[t for t in entity.trends if t.field.name == name],
                    start_position=store.position,
                    trend_state=store.trend_state,
                )
            )
            row[name] = generated[name]
            store.position += 1
            continue
        [generated] = list(iter_rows([fields_by_name[name]], 1))
        row[name] = generated[name]
    return row


def _changeable_field_names(store: RecordStore, requested: list[str] | None) -> list[str]:
    identity_name = store.identity_field.name
    available = [f.name for f in store.entity.fields if f.name != identity_name and not f.formula]
    if requested is None:
        return available
    unknown = [name for name in requested if name not in available]
    if unknown:
        raise ContinuityError(
            f"Cannot update {', '.join(unknown)} — not a changeable field on "
            f"'{store.entity.name}' (the identity field and formula fields are derived)"
        )
    return requested


def apply_changes(
    db: Session,
    store: RecordStore,
    inserts: int = 0,
    updates: int = 0,
    deletes: int = 0,
    update_fields: list[str] | None = None,
    fk_pools: dict[str, list[Any]] | None = None,
    event_time: datetime | None = None,
) -> list[ChangeEvent]:
    """Move the population forward one tick and return what changed.

    Inserts, then updates, then deletes, and that order is deliberate: a
    record inserted by this call is eligible to be updated by it, which is
    what a busy table actually looks like, while a record deleted by this
    call cannot then be updated by it — a consumer must never see an update
    to something already dropped.

    Updates and deletes draw from the live population without replacement,
    so one record cannot be updated twice in a single tick and reach the
    consumer as two events at the same instant.
    """
    events: list[ChangeEvent] = []
    at = event_time or datetime.now(UTC)

    if inserts:
        generate_new(db, store, inserts, fk_pools=fk_pools, event_time=at)

    names = _changeable_field_names(store, update_fields)

    live = _active_records(db, store)
    random.shuffle(live)

    if updates:
        if not names:
            raise ContinuityError(
                f"'{store.entity.name}' has no field an update could change — every "
                "field is either the identity or derived from a formula"
            )
        for record in live[:updates]:
            before = dict(record.data)
            after = _updated_row(store, record, names)
            record.data = after
            record.version += 1
            # Close the old version at the same instant the new one opens,
            # so the intervals tile the timeline with no gap a query could
            # fall into.
            _close_version(db, store, record.identity, at)
            _open_version(db, store, record.identity, record.version, after, at)
            events.append(
                _log(
                    db,
                    store,
                    ChangeOperation.UPDATE,
                    record.identity,
                    before=before,
                    after=after,
                    version=record.version,
                    event_time=at,
                )
            )
        live = live[updates:]

    if deletes:
        for record in live[:deletes]:
            record.status = RecordStatus.DELETED
            record.version += 1
            # A deleted record's last version closes and no new one opens:
            # after this instant there is no truth about it to record, which
            # is different from a version whose values happen to be null.
            _close_version(db, store, record.identity, at)
            events.append(
                _log(
                    db,
                    store,
                    ChangeOperation.DELETE,
                    record.identity,
                    before=dict(record.data),
                    after=None,
                    version=record.version,
                    event_time=at,
                )
            )

    db.flush()
    return events


def read_changes(
    db: Session, store: RecordStore, after: int = -1, limit: int = 100
) -> list[ChangeEvent]:
    """Events after a cursor, oldest first.

    `after` is exclusive and defaults to -1 so the first read starts at
    sequence 0. A consumer stores the last sequence it handled and passes it
    back — the same contract as a Kafka offset or a replication slot.
    """
    return list(
        db.scalars(
            select(ChangeEvent)
            .where(ChangeEvent.store_id == store.id)
            .where(ChangeEvent.sequence > after)
            .order_by(ChangeEvent.sequence)
            .limit(limit)
        ).all()
    )


def delete_events_before(db: Session, store: RecordStore, sequence: int) -> int:
    """Trim the change log up to (not including) `sequence`.

    The log is bounded by churn rather than output volume, but a store
    driven hard for long enough still accumulates. Trimming is explicit
    rather than automatic: only the operator knows whether every consumer
    has caught up, and dropping events a consumer has not read yet turns a
    replayable stream into a lossy one.
    """
    stale = list(
        db.scalars(
            select(ChangeEvent)
            .where(ChangeEvent.store_id == store.id)
            .where(ChangeEvent.sequence < sequence)
        ).all()
    )
    for event in stale:
        db.delete(event)
    db.flush()
    return len(stale)


# --------------------------------------------------------------------------
# Slowly-changing dimensions and backfill
# --------------------------------------------------------------------------


def versions_of(db: Session, store: RecordStore, identity: str) -> list[RecordVersion]:
    """Every version of one record, oldest first."""
    return list(
        db.scalars(
            select(RecordVersion)
            .where(RecordVersion.store_id == store.id)
            .where(RecordVersion.identity == identity)
            .order_by(RecordVersion.version)
        ).all()
    )


def snapshot_at(db: Session, store: RecordStore, moment: datetime) -> list[RecordVersion]:
    """The population as it stood at `moment`.

    The question a type 2 dimension exists to answer, and one a type 1 store
    cannot answer at all: it kept no past to look at. The interval is
    closed-open — `valid_from <= moment < valid_to` — so a record that
    changed exactly at `moment` is reported with its new values, not two
    rows.
    """
    if store.scd_type != SCDType.TYPE_2:
        raise ContinuityError(
            "This store keeps no history. A point-in-time snapshot needs SCD type 2 — "
            "type 1 overwrites, so there is no past to look at."
        )
    return list(
        db.scalars(
            select(RecordVersion)
            .where(RecordVersion.store_id == store.id)
            .where(RecordVersion.valid_from <= moment)
            .where((RecordVersion.valid_to.is_(None)) | (RecordVersion.valid_to > moment))
            .order_by(RecordVersion.identity)
        ).all()
    )


def backfill(
    db: Session,
    store: RecordStore,
    start: datetime,
    end: datetime,
    ticks: int,
    inserts: int = 0,
    updates: int = 0,
    deletes: int = 0,
    update_fields: list[str] | None = None,
    fk_pools: dict[str, list[Any]] | None = None,
) -> list[ChangeEvent]:
    """Run `ticks` ticks of churn spread evenly across a past window.

    A test system usually needs a history before it needs a present: an ETL
    pipeline being developed against an empty table has nothing to
    aggregate, and a dashboard with one day of data cannot be checked
    against a month-over-month figure. This produces that history in one
    call, and — because the store's cursor, workflow states and identities
    all carry forward — live generation afterwards continues from the end of
    it rather than starting a second, unrelated universe. That continuity is
    the reason backfill belongs here and not in a script.

    Each tick is stamped with its own `event_time`, so the change log and
    any SCD type 2 intervals are spread across the window rather than
    collapsed into the instant the request was made. `created_at` still says
    now, because that is when the rows were written; conflating the two
    would make a backfilled year look like one very busy second.

    Refuses to run backwards or into the future. A window whose end precedes
    its start would produce events in an order no consumer could read, and
    dating changes ahead of now would make the *next* live tick look like it
    happened in the past.
    """
    if end <= start:
        raise ContinuityError("A backfill window must end after it starts")
    if ticks < 1:
        raise ContinuityError("A backfill needs at least one tick")
    now = datetime.now(UTC)
    if end > now:
        raise ContinuityError(
            "A backfill window cannot end in the future — the next live tick would "
            "then look like it happened in the past"
        )

    # A backfill has to be the store's first activity. This is stricter than
    # "the window must precede what exists", and deliberately so: the
    # problem is not only the window but the *records*. A record created
    # today has a version starting today, so a backfilled update dated last
    # week closes that version before it opened — `valid_from` after
    # `valid_to`. Dating new inserts in the past while existing rows sit at
    # "now" separately breaks the cursor contract, because sequence order
    # would stop matching event order for a consumer reading by time.
    #
    # Found by looking at the UI, not by the suite: generate, then backfill,
    # then open the version history, and the first interval runs backwards.
    existing = db.scalar(
        select(func.count()).select_from(ChangeEvent).where(ChangeEvent.store_id == store.id)
    )
    if existing:
        raise ContinuityError(
            f"This store already has {existing} recorded changes. A backfill writes "
            "history, so it has to come first — otherwise records created today get "
            "versions that end before they start, and the change log runs out of order. "
            "Backfill into a new store, then generate live from the end of it."
        )

    step = (end - start) / ticks
    events: list[ChangeEvent] = []
    for index in range(ticks):
        # The tick's own instant, not the window's start: `ticks` ticks all
        # dated `start` would be a backfill in name only.
        at = start + step * index
        events.extend(
            apply_changes(
                db,
                store,
                inserts=inserts,
                updates=updates,
                deletes=deletes,
                update_fields=update_fields,
                fk_pools=fk_pools,
                event_time=at,
            )
        )
    return events


def default_backfill_window(days: int = 30) -> tuple[datetime, datetime]:
    """A window ending now. Convenience for the common "last N days" ask."""
    now = datetime.now(UTC)
    return now - timedelta(days=days), now
