"""Add record stores and stored records -- Phase 13

The tables behind persistent record identity: a `RecordStore` is a
population of one entity's records that survives between generation calls,
and a `StoredRecord` is one member of it.

`identity_field_id` is NOT NULL by design. A store that cannot say what
makes two rows the same record cannot offer identity at all — see the model
docstring for why a hidden surrogate key would have been worse than
refusing.

Unlike the MongoDB-dialect and object-storage migrations, this
`downgrade()` is real. Both of those were irreversible because they added a
value to an existing Postgres enum and there is no
`ALTER TYPE ... DROP VALUE`; this one *creates* its enum, so dropping it is
sound. It has to be dropped explicitly — Postgres leaves the type behind
when the only table using it goes away, and an `upgrade` after that
`downgrade` would then fail on a type that already exists.

Revision ID: aad4f3c56223
Revises: 2589ca4a7793
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "aad4f3c56223"
down_revision: str | None = "2589ca4a7793"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "record_stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("identity_field_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("trend_state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_field_id"], ["entity_fields.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "name", name="uq_record_store_entity_name"),
    )
    op.create_table(
        "stored_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("identity", sa.String(length=512), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "DELETED", name="recordstatus"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["store_id"], ["record_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "identity", name="uq_stored_record_store_identity"),
    )
    op.create_index(
        op.f("ix_stored_records_store_id"), "stored_records", ["store_id"], unique=False
    )
    op.create_index(
        op.f("ix_stored_records_sequence"), "stored_records", ["sequence"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stored_records_sequence"), table_name="stored_records")
    op.drop_index(op.f("ix_stored_records_store_id"), table_name="stored_records")
    op.drop_table("stored_records")
    op.drop_table("record_stores")
    # Explicit: Postgres keeps an enum type after its last table is dropped,
    # so leaving this out would make the next `upgrade` fail on a type that
    # already exists. `checkfirst` keeps it a no-op on SQLite, which has no
    # enum types at all.
    sa.Enum(name="recordstatus").drop(op.get_bind(), checkfirst=True)
