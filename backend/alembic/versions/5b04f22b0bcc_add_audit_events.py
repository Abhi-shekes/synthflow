"""Add the audit log -- Phase 14

One row per mutating request, written by middleware rather than by calls
inside the routes. See `models.audit.AuditEvent` for why: a log assembled by
remembering to log has invisible holes.

`user_id` is nullable with `ON DELETE SET NULL`, not CASCADE. Deleting a user
must not delete the record of what they did — that is the one deletion an
audit log exists to survive. `actor_email` and `api_key_prefix` are
denormalised alongside it so an event can still name who did it after the
user or the key is gone.

`project_id` is a plain indexed column rather than a foreign key. It is
lifted out of the request's path parameters, which may name a project that
has since been deleted, and a foreign key would either block that deletion or
erase the history of it.

Three indexes, each earning its place: `user_id` and `project_id` because
those are the two questions ("what did I do", "what happened to this
project"), and `created_at` because every read of this table is ordered by
it.

Revision ID: 5b04f22b0bcc
Revises: 34d5b5191e38
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b04f22b0bcc"
down_revision: str | None = "34d5b5191e38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column(
            "actor_kind",
            sa.Enum("SESSION", "API_KEY", name="actorkind"),
            nullable=False,
        ),
        sa.Column("api_key_prefix", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("route", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("path_params", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"])
    op.create_index(op.f("ix_audit_events_project_id"), "audit_events", ["project_id"])
    op.create_index(op.f("ix_audit_events_user_id"), "audit_events", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_user_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_project_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_table("audit_events")
    sa.Enum(name="actorkind").drop(op.get_bind(), checkfirst=True)
