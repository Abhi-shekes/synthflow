"""Add per-relationship link counts for true many-to-many -- Phase 13

`min_links`/`max_links` say how many targets each source row links to in a
many-to-many join table. They apply to that type only; the other three
relationship types keep a foreign key on a row and have nothing to count.

Both are NOT NULL on a table that already holds relationships, so both ship
with a server default that is dropped immediately afterwards — 1 and 3, the
same defaults the model declares. Leaving the defaults in place would let a
bug that forgets to set them pass silently.

Existing `many_to_many` rows get these values and, from this release, a real
join table rather than the one-to-many behaviour they used to get. That is a
deliberate behaviour change to a documented simplification, recorded in
ROADMAP.md rather than smuggled in: a project that modelled a many-to-many
as a foreign key on the source row was really modelling a one-to-many, and
the type now means what it says.

Revision ID: c3566cce5327
Revises: f9c7c3cdc952
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3566cce5327"
down_revision: str | None = "f9c7c3cdc952"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "relationships",
        sa.Column("min_links", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "relationships",
        sa.Column("max_links", sa.Integer(), nullable=False, server_default="3"),
    )
    op.alter_column("relationships", "min_links", server_default=None)
    op.alter_column("relationships", "max_links", server_default=None)


def downgrade() -> None:
    op.drop_column("relationships", "max_links")
    op.drop_column("relationships", "min_links")
