"""add ui_mode and has_onboarded to users

Revision ID: a1b2c3d4e5f6
Revises: df6fd2ae4adf
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'df6fd2ae4adf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('ui_mode', sa.String(length=20), nullable=False, server_default='guided'),
    )
    op.add_column(
        'users',
        sa.Column(
            'has_onboarded', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'has_onboarded')
    op.drop_column('users', 'ui_mode')
