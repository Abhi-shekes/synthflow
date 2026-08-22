"""Add a per-field null probability -- Phase 9 debt

Closes the one thing profiling could measure and not reproduce. A column
observed to be 3% empty produced a field that generated nulls 15% of the
time, because `generator.NULLABLE_PROBABILITY` was a flat constant and there
was nowhere on the field to say otherwise.

**Nullable, with no default, on purpose.** NULL here means "this field never
expressed an opinion, use the engine default" — which is exactly what every
existing field meant before this column existed, so no existing row's
behaviour changes. That is deliberately distinct from an explicit `0.0`,
which means "never null" and is a real thing to ask for. Backfilling 0.15
would have made every field claim a rate nobody chose, and made the two
cases indistinguishable forever after.

Revision ID: df6fd2ae4adf
Revises: d7d088bafef7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "df6fd2ae4adf"
down_revision: str | None = "d7d088bafef7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("entity_fields", sa.Column("null_probability", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("entity_fields", "null_probability")
