import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.project import Project


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobFormat(enum.StrEnum):
    """How a job's rows are written.

    Every one of these streams, which is the rule rather than a
    coincidence: a job exists precisely for output too large to hold in
    memory, so a format needing the whole result before the first byte (a
    JSON array, an Excel workbook) is deliberately absent. Parquet and ORC
    qualify because they are built from row groups and
    app.services.row_writers emits one per chunk; Avro is
    block-structured and behaves the same way.

    The columnar three need optional extras — see
    app.services.row_writers.REQUIRED_EXTRA."""

    CSV = "csv"
    JSONL = "jsonl"
    PARQUET = "parquet"
    ORC = "orc"
    AVRO = "avro"


class GenerationJob(Base):
    """A generation run that happens outside the request/response cycle.

    The interactive `POST .../generate` route is capped at
    `MAX_GENERATE_ROWS` because it builds the whole batch in memory and
    returns it in one response. A job removes both limits: rows are
    streamed to a file via `app.services.generator.iter_rows`, so peak
    memory is a single row regardless of `requested_rows`.

    **This table is also the queue.** Workers claim rows with
    `SELECT ... FOR UPDATE SKIP LOCKED` (see app.services.jobs), which is
    the standard way to build a job queue on a relational database and
    means three things fall out for free rather than needing new
    infrastructure:

    - Jobs survive a restart by construction — they're rows, not
      in-process state, so an interrupted job is simply still `running`
      with a stale lock and gets reclaimed.
    - Exactly one worker runs a given job, which is the "distributed
      locking" this phase needed.
    - No Redis or separate broker container. That's a deliberate
      deviation from the tech-stack table's original "Celery, Redis" —
      see ROADMAP Phase 8 for the reasoning.

    Known limit, documented rather than hidden: `SKIP LOCKED` is a
    PostgreSQL feature. On SQLite (local dev and the test suite) claiming
    falls back to a plain conditional UPDATE, which is safe for a single
    worker but not for several. Running multiple workers is a Postgres
    deployment concern anyway.
    """

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Null means "the whole project", matching POST /projects/{id}/generate.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True
    )

    status: Mapped[JobStatus] = mapped_column(
        String(20), nullable=False, default=JobStatus.QUEUED, index=True
    )
    format: Mapped[JobFormat] = mapped_column(String(10), nullable=False, default=JobFormat.CSV)
    requested_rows: Mapped[int] = mapped_column(Integer, nullable=False)

    # Updated as the job streams, so progress is observable while it runs
    # rather than only at the end.
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    artifacts: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Optional upload destination. Null means "leave the file on disk",
    # which stays the default so nothing changes for anyone not using
    # object storage — see app.services.object_storage.
    storage_target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("object_storage_targets.id", ondelete="SET NULL"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when a worker claims the job; the pair is what makes a stale
    # lock (worker died mid-run) detectable and reclaimable.
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cooperative cancellation: the API sets this, the streaming loop
    # checks it between chunks. A running job can't be killed mid-write
    # without leaving a half-file, so it stops at a chunk boundary.
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship()
    entity: Mapped["Entity"] = relationship()


class Schedule(Base):
    """A recurring generation job.

    Deliberately reuses `GenerationJob` rather than running work itself:
    when a schedule is due, the worker inserts an ordinary queued job and
    moves on. So a scheduled run has exactly the same history, progress,
    cancellation and artifacts as a manual one, and there's one execution
    path to keep correct instead of two.

    `cron` is a standard five-field expression, evaluated by
    `app.services.cron` — a small parser rather than a dependency, since
    the only thing needed is "when is the next time after X".
    """

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron: Mapped[str] = mapped_column(String(100), nullable=False)
    format: Mapped[JobFormat] = mapped_column(String(10), nullable=False, default=JobFormat.CSV)
    requested_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship()
    entity: Mapped["Entity"] = relationship()
