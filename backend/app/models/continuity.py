import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.field import EntityField


class RecordStatus(enum.StrEnum):
    """Whether a stored record is still part of the live population.

    Deletes are `DELETED`, not row removals. A CDC consumer needs to be told
    a record went away, and a row that has been deleted from the table
    cannot tell anyone anything — the tombstone is the whole point, and it
    is also what lets a delete event be replayed.
    """

    ACTIVE = "active"
    DELETED = "deleted"


class RecordStore(Base):
    """A population of records for one entity that survives between
    generation calls.

    Every generation call before Phase 13 produced a fresh unrelated
    universe: ask for 100 customers twice and you get 200 strangers. That is
    correct for seeding a test database once and wrong for almost everything
    that consumes a *stream* — a CDC pipeline, an ETL job, a dashboard
    watching a table change. A store is where "the same customer, yesterday
    and today" is kept.

    **`identity_field` is required, and that is a deliberate constraint.**
    Persistent identity means knowing what makes two rows the same record,
    and only the schema's author knows that. The alternative — quietly
    minting a surrogate key the generated output never shows — would be
    identity in name only: nothing downstream could join on it, so a
    consumer could not tell an update from an unrelated insert, which is
    precisely the thing this exists to make possible.

    **Scoped per store, not per entity.** One entity can back several
    independent stores, because two consumers of the same schema are not
    watching the same population: a demo stream and a nightly ETL feed
    should not hand each other half-consumed state. `name` is unique per
    entity, so a caller addresses a store by a name it chose rather than
    having to remember a UUID.

    **`position` is the cursor Phase 4 never had.** Trends and geo routes
    make a value a function of a row's position *within the current batch*,
    which is why a trend replays from its start on every call and a
    WebSocket stream sawtooths instead of rising. The store carries that
    position forward, so the second batch of a linear trend continues where
    the first stopped. `trend_state` does the same job for `random_walk`,
    whose running value is otherwise rebuilt from `start` every call.

    **What this is not.** A store holds a *population*, not an output log. A
    10-million-row generation job does not put ten million rows in Postgres;
    it draws from a store of the records that persist and writes the rest to
    its file. Keeping every emitted row would turn the control-plane
    database into the data plane, which is the one thing Phase 8's streaming
    design exists to avoid.
    """

    __tablename__ = "record_stores"
    __table_args__ = (UniqueConstraint("entity_id", "name", name="uq_record_store_entity_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Not nullable on purpose — see the class docstring. A store that cannot
    # say what identifies a record cannot offer persistent identity.
    identity_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), nullable=False
    )

    # Rows emitted through this store so far. Feeds trend and geo-route
    # position, so a curve continues across calls instead of restarting.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-trend running state, keyed by trend id. Only `random_walk` uses it
    # today; it is a dict rather than a column so a future stateful trend
    # type needs no migration.
    trend_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity: Mapped["Entity"] = relationship()
    identity_field: Mapped["EntityField"] = relationship()
    records: Mapped[list["StoredRecord"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


class StoredRecord(Base):
    """One record that persists across generation calls.

    `identity` is the stringified value of the store's identity field. It is
    text regardless of the field's own type because it is only ever compared
    for equality and used as a key — storing an int in one row and a UUID in
    another under one column means one type, and the alternative (a column
    per field type) buys nothing.

    `version` starts at 1 and increments on every update, which is what
    makes a CDC `update` event distinguishable from a replay of the same
    one. `data` is the record's *current* values; earlier versions live in
    `StoredRecordVersion` only when the store is asked to keep them, because
    most consumers want the current row and paying for history nobody reads
    is how a control-plane database stops fitting on disk.
    """

    __tablename__ = "stored_records"
    __table_args__ = (
        UniqueConstraint("store_id", "identity", name="uq_stored_record_store_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("record_stores.id", ondelete="CASCADE"), index=True
    )
    identity: Mapped[str] = mapped_column(String(512), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # The store's cursor when this record was created, which makes "the
    # order they arrived in" a real column rather than something inferred.
    # `created_at` cannot do that job: every record written by one call
    # shares a transaction timestamp to the microsecond, so ordering by it
    # falls back to a tiebreaker and a batch comes back shuffled. A CDC
    # consumer replaying changes needs a total order, and this is it.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), nullable=False, default=RecordStatus.ACTIVE
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    store: Mapped["RecordStore"] = relationship(back_populates="records")
