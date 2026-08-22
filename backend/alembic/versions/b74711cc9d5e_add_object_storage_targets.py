"""Add object storage targets, and let a job upload to one

`secret_access_key` is declared here as a plain String rather than the
application's `EncryptedString`. At the database level that is exactly what
the column is — the encryption lives in the SQLAlchemy type, not in the DDL
— and a migration that imports application code freezes today's definition
into a file that must keep working years from now. Phase 10's migration
imports `app.core.secrets` deliberately, but only because it performs a
*data* step and the encryption scheme must be defined in one place; there
is no data step here.

The foreign key is named explicitly. Autogenerate emitted
`op.drop_constraint(None, ...)`, which cannot work on Postgres, where a
constraint must be dropped by name.

Revision ID: b74711cc9d5e
Revises: c9f3a1d75b60
"""

import sqlalchemy as sa
from alembic import op

revision = "b74711cc9d5e"
down_revision = "c9f3a1d75b60"
branch_labels = None
depends_on = None

_FK_NAME = "fk_generation_jobs_storage_target_id"


def upgrade() -> None:
    op.create_table(
        "object_storage_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.Enum("S3", name="storageprovider"), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=512), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("endpoint_url", sa.String(length=512), nullable=False),
        sa.Column("access_key_id", sa.String(length=255), nullable=False),
        sa.Column("secret_access_key", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("generation_jobs", sa.Column("storage_target_id", sa.Uuid(), nullable=True))
    # SET NULL rather than CASCADE: deleting a storage target must not
    # delete the history of jobs that once uploaded to it.
    op.create_foreign_key(
        _FK_NAME,
        "generation_jobs",
        "object_storage_targets",
        ["storage_target_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    with op.batch_alter_table("generation_jobs") as batch:
        batch.drop_constraint(_FK_NAME, type_="foreignkey")
        batch.drop_column("storage_target_id")
    op.drop_table("object_storage_targets")
    sa.Enum(name="storageprovider").drop(op.get_bind(), checkfirst=True)
