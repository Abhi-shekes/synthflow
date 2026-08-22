"""Add MONGODB to the database_connections dialect enum

Postgres stores this column as a native ENUM type, so a new dialect is a
schema change rather than just a Python-side constant. `IF NOT EXISTS`
makes it idempotent, which matters because a database created fresh from
the models already has the value and would otherwise fail here.

**This migration cannot be reversed.** Postgres has no
`ALTER TYPE ... DROP VALUE`; removing an enum member means recreating the
type and rewriting every column that uses it. Doing that automatically, on
a downgrade, against a table that may hold live MongoDB connections, is a
worse outcome than refusing — so `downgrade` deliberately does nothing and
says why. Downgrading past this point leaves an unused enum value behind,
which is harmless: nothing reads it once the application no longer offers
MongoDB.

Revision ID: c9f3a1d75b60
Revises: b41d7c9e0f52
"""

from alembic import op

revision = "c9f3a1d75b60"
down_revision = "b41d7c9e0f52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (dev and tests) stores this as VARCHAR, so the value is
        # already accepted with no schema change needed.
        return
    op.execute("ALTER TYPE databasedialect ADD VALUE IF NOT EXISTS 'MONGODB'")


def downgrade() -> None:
    """Intentionally a no-op — see the module docstring."""
