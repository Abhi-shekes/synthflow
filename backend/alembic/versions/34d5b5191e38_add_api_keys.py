"""Add API keys -- Phase 14

Long-lived credentials for machines. Until now the only authentication was a
user-password login producing a short-lived JWT, so there was no supported
way to call SynthFlow from CI at all.

`key_hash` is a 64-character hex SHA-256 digest, not a bcrypt hash, and the
column width says so. That is a deliberate departure from how `users`
stores a password: an API key is 32 random bytes, so there is nothing to
guess and bcrypt's slowness would cost every request while buying nothing.

`prefix` is unique and indexed because verification is a lookup by prefix
followed by one constant-time compare — without it, checking a key would
mean hashing against every row in the table.

Revocation is a nullable timestamp rather than a row deletion, so a revoked
key stays visible to anyone investigating an incident.

`downgrade()` drops the enum type explicitly; Postgres keeps it after the
last table using it goes away.

Revision ID: 34d5b5191e38
Revises: c3566cce5327
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "34d5b5191e38"
down_revision: str | None = "c3566cce5327"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scope",
            sa.Enum("READ_ONLY", "FULL", name="apikeyscope"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_prefix"), "api_keys", ["prefix"], unique=True)
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_prefix"), table_name="api_keys")
    op.drop_table("api_keys")
    sa.Enum(name="apikeyscope").drop(op.get_bind(), checkfirst=True)
