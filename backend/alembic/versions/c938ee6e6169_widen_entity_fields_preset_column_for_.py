"""widen entity_fields preset column for plugin names

Revision ID: c938ee6e6169
Revises: ac69cac79acc
Create Date: 2026-08-21 19:56:21.129049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c938ee6e6169'
down_revision: Union[str, None] = 'ac69cac79acc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table because SQLite (used for local dev/tests) has no
    # native ALTER COLUMN TYPE — this recreates the table under the hood on
    # SQLite, and is just a normal ALTER on Postgres.
    with op.batch_alter_table('entity_fields') as batch_op:
        batch_op.alter_column(
            'preset',
            existing_type=sa.VARCHAR(length=50),
            type_=sa.String(length=100),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('entity_fields') as batch_op:
        batch_op.alter_column(
            'preset',
            existing_type=sa.String(length=100),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
