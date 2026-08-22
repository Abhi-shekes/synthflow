"""Add rabbitmq and webhook outputs

Both secrets — `rabbitmq_outputs.password` and `webhook_outputs.secret` —
are declared as plain String here rather than the application's
`EncryptedString`. At the database level that is exactly what they are: the
encryption lives in the SQLAlchemy type, not in the DDL, and a migration
that imports application code freezes today's definition into a file that
has to keep working years from now. Same reasoning as the object-storage
migration.

Revision ID: 2589ca4a7793
Revises: b74711cc9d5e
"""

import sqlalchemy as sa
from alembic import op

revision = "2589ca4a7793"
down_revision = "b74711cc9d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rabbitmq_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("vhost", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=1024), nullable=False),
        sa.Column("exchange", sa.String(length=255), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column("events_per_second", sa.Float(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "webhook_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("secret", sa.String(length=1024), nullable=False),
        sa.Column("events_per_second", sa.Float(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("webhook_outputs")
    op.drop_table("rabbitmq_outputs")
