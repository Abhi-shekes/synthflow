"""Encrypt database_connections.password at rest

Widens the column (a Fernet token is much longer than the plaintext) and
encrypts any password already stored, so an existing install stops holding
plaintext credentials the moment it upgrades rather than only for
connections saved afterwards.

The data step is written against app.core.secrets rather than reimplementing
the scheme, so the prefix and key derivation can only ever be defined in one
place. Rows are skipped if already encrypted, which makes this safe to re-run
and safe against a half-applied migration.

Downgrade decrypts back to plaintext. That is a genuine downgrade in security
and is only there because a migration that cannot be reversed blocks a
rollback — if SECRET_KEY is unavailable the decrypt fails, and the migration
stops rather than writing unreadable values back.

Revision ID: b41d7c9e0f52
Revises: e27c4642c406
"""

import sqlalchemy as sa
from alembic import op

from app.core.secrets import decrypt_secret, encrypt_secret, is_encrypted

revision = "b41d7c9e0f52"
down_revision = "e27c4642c406"
branch_labels = None
depends_on = None

# Only the columns needed for the data step — deliberately not the ORM
# model, which will drift away from this migration over time.
_connections = sa.table(
    "database_connections",
    sa.column("id", sa.Uuid()),
    sa.column("password", sa.String()),
)


def upgrade() -> None:
    op.alter_column(
        "database_connections",
        "password",
        existing_type=sa.String(length=255),
        type_=sa.String(length=1024),
        existing_nullable=False,
    )

    bind = op.get_bind()
    for row in bind.execute(sa.select(_connections.c.id, _connections.c.password)):
        if not row.password or is_encrypted(row.password):
            continue
        bind.execute(
            _connections.update()
            .where(_connections.c.id == row.id)
            .values(password=encrypt_secret(row.password))
        )


def downgrade() -> None:
    bind = op.get_bind()
    for row in bind.execute(sa.select(_connections.c.id, _connections.c.password)):
        if not row.password or not is_encrypted(row.password):
            continue
        bind.execute(
            _connections.update()
            .where(_connections.c.id == row.id)
            .values(password=decrypt_secret(row.password))
        )

    op.alter_column(
        "database_connections",
        "password",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
