"""Add SCD type 2 versions, and an event time distinct from a write time -- Phase 13

Two NOT NULL columns land on tables that already hold rows, so both get a
backfill rather than a bare `add_column`, which would fail outright.

`change_events.event_time` is backfilled from `created_at`. That is the
honest value and not merely a convenient one: for every event written before
this column existed, the moment it was recorded *was* the moment it
happened. Only a backfill separates the two, and no backfill can have run
yet.

`record_stores.scd_type` defaults to TYPE_1, which is what every existing
store already did — it overwrote. Both server defaults are dropped
immediately afterwards so the application stays the only thing choosing a
value; leaving them would let a bug that forgets to set one pass silently.

The Postgres enum stores member *names* (`TYPE_1`), matching how
`Enum(RecordStatus)` behaves in the migration two revisions back, so the
default is written that way too.

`downgrade()` drops the enum type explicitly — Postgres keeps it after the
last table using it goes away, and the next `upgrade` would then fail on a
type that already exists.

Revision ID: f9c7c3cdc952
Revises: c940da362c39
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9c7c3cdc952"
down_revision: str | None = "c940da362c39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCD_TYPE = sa.Enum("TYPE_1", "TYPE_2", name="scdtype")


def upgrade() -> None:
    op.create_table(
        "record_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("identity", sa.String(length=512), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["store_id"], ["record_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_record_versions_identity"), "record_versions", ["identity"], unique=False
    )
    op.create_index(
        op.f("ix_record_versions_store_id"), "record_versions", ["store_id"], unique=False
    )

    op.add_column(
        "change_events",
        sa.Column(
            "event_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # For an event recorded before this column existed, when it was written
    # is when it happened. Nothing else could be true yet.
    op.execute("UPDATE change_events SET event_time = created_at")
    op.alter_column("change_events", "event_time", server_default=None)
    op.create_index(
        op.f("ix_change_events_event_time"), "change_events", ["event_time"], unique=False
    )

    SCD_TYPE.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "record_stores",
        sa.Column("scd_type", SCD_TYPE, nullable=False, server_default="TYPE_1"),
    )
    op.alter_column("record_stores", "scd_type", server_default=None)


def downgrade() -> None:
    op.drop_column("record_stores", "scd_type")
    SCD_TYPE.drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_change_events_event_time"), table_name="change_events")
    op.drop_column("change_events", "event_time")

    op.drop_index(op.f("ix_record_versions_store_id"), table_name="record_versions")
    op.drop_index(op.f("ix_record_versions_identity"), table_name="record_versions")
    op.drop_table("record_versions")
