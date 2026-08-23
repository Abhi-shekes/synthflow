"""Add organizations, membership roles, and project sharing -- Phase 14

`projects.organization_id` is nullable, and every existing project keeps it
null. That is the whole compatibility story: a project without an
organisation is personal and behaves exactly as it did before, so this
migration changes no existing row's meaning.

`ON DELETE SET NULL` on that foreign key, not CASCADE. Dissolving an
organisation must return its projects to their owners, not destroy them —
deleting other people's work as a side effect of tidying up a group would be
a spectacular way to lose data.

The unique constraint on (organization_id, user_id) is in the database
rather than in application code because two rows for one person with
different roles is a question with no correct answer, and only the database
can refuse it under concurrency.

`downgrade()` drops the enum type explicitly; Postgres keeps it after the
last table using it goes away.

Revision ID: 7dbd6867fc76
Revises: 5b04f22b0bcc
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7dbd6867fc76"
down_revision: str | None = "5b04f22b0bcc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = sa.Enum("VIEWER", "MEMBER", "ADMIN", "OWNER", name="role")


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )
    op.create_index(
        op.f("ix_organization_members_organization_id"),
        "organization_members",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_organization_members_user_id"), "organization_members", ["user_id"]
    )

    # batch_alter_table: SQLite has no ALTER to add a constraint to an
    # existing table (only batch mode's recreate-copy-swap can do it), so
    # the bare add_column/create_foreign_key this replaced only ever worked
    # against Postgres.
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(op.f("ix_projects_organization_id"), "projects", ["organization_id"])


def downgrade() -> None:
    # Named explicitly. Autogenerate emitted `drop_constraint(None, ...)`,
    # which cannot work on Postgres, where a constraint is dropped by name —
    # the same correction the object-storage migration needed.
    op.drop_index(op.f("ix_projects_organization_id"), table_name="projects")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")

    op.drop_index(op.f("ix_organization_members_user_id"), table_name="organization_members")
    op.drop_index(
        op.f("ix_organization_members_organization_id"), table_name="organization_members"
    )
    op.drop_table("organization_members")
    op.drop_table("organizations")
    ROLE.drop(op.get_bind(), checkfirst=True)
