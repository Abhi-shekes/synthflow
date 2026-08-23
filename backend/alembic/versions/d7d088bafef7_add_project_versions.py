"""Add project version history -- Phase 14

A snapshot of a project's *design*, stored as the same `ProjectTemplate`
payload export and import already use. Reusing that format is why this
needed one table rather than a parallel schema that would have drifted from
the real one the first time a field type was added.

`(project_id, version)` is unique. Version numbers are per project and
human-facing ("v3"), and they come from `projects.next_version_number` —
a real counter, added here — rather than `max(version) + 1` over the
existing rows. Deleting the most recent snapshot lowers that maximum, so the
next snapshot would reuse a number somebody may have referred to last week,
and "roll back to v3" would quietly mean a different design.

`created_by_id` is `ON DELETE SET NULL` with the email denormalised beside
it, the same rule the audit log follows: deleting a user must not delete the
history of what the project looked like.

Revision ID: d7d088bafef7
Revises: 7dbd6867fc76
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7d088bafef7"
down_revision: str | None = "7dbd6867fc76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("template", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_project_version_project_version"),
    )
    op.create_index(op.f("ix_project_versions_project_id"), "project_versions", ["project_id"])

    # NOT NULL on a table that already has rows, so it ships with a server
    # default that is dropped immediately after — every existing project
    # starts at v1. Leaving the default in place would let a bug that
    # forgets to advance the counter pass silently.
    op.add_column(
        "projects",
        sa.Column("next_version_number", sa.Integer(), nullable=False, server_default="1"),
    )
    # batch_alter_table: SQLite has no ALTER COLUMN, so dropping the default
    # (bare alter_column) only ever worked against Postgres.
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("next_version_number", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "next_version_number")
    op.drop_index(op.f("ix_project_versions_project_id"), table_name="project_versions")
    op.drop_table("project_versions")
