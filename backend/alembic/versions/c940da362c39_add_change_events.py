"""Add the change log behind CDC-shaped generation -- Phase 13

A `ChangeEvent` is one insert, update or delete against a store's
population, in the order it happened. `record_stores.change_sequence` is the
counter events are numbered from — separate from `position`, which counts
rows *generated*: an update and a delete move no trend forward but are both
events a consumer has to see in order.

`change_sequence` ships with `server_default="0"`, which autogenerate left
out. A NOT NULL column with no default cannot be added to a table that
already holds rows, and by the time this runs a store created by the
previous migration may well hold some. The default is dropped immediately
afterwards so the application stays the only thing deciding the value —
leaving it in place would mean a bug that forgets to set it silently
produces a store whose log restarts at zero.

`downgrade()` drops the enum type explicitly. Postgres keeps it after the
last table using it goes away, so without this the next `upgrade` fails on a
type that already exists.

Revision ID: c940da362c39
Revises: aad4f3c56223
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c940da362c39"
down_revision: str | None = "aad4f3c56223"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("INSERT", "UPDATE", "DELETE", name="changeoperation"),
            nullable=False,
        ),
        sa.Column("identity", sa.String(length=512), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["store_id"], ["record_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "sequence", name="uq_change_event_store_sequence"),
    )
    op.create_index(op.f("ix_change_events_store_id"), "change_events", ["store_id"], unique=False)

    op.add_column(
        "record_stores",
        sa.Column("change_sequence", sa.Integer(), nullable=False, server_default="0"),
    )
    # batch_alter_table: SQLite has no ALTER COLUMN, so dropping the default
    # (bare alter_column) only ever worked against Postgres.
    with op.batch_alter_table("record_stores") as batch_op:
        batch_op.alter_column("change_sequence", server_default=None)


def downgrade() -> None:
    op.drop_column("record_stores", "change_sequence")
    op.drop_index(op.f("ix_change_events_store_id"), table_name="change_events")
    op.drop_table("change_events")
    sa.Enum(name="changeoperation").drop(op.get_bind(), checkfirst=True)
