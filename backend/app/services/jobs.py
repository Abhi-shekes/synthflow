"""The background worker: claims jobs, streams them to disk, and turns
due schedules into jobs.

Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`, the standard way to
build a queue on a relational database. Two workers asking for work at
the same instant get different rows rather than fighting over one, so
"exactly one worker runs a given job" is enforced by the database instead
of by a lock service. On SQLite (dev and tests) `SKIP LOCKED` doesn't
exist, so claiming degrades to a conditional UPDATE — safe for one
worker, not for several, which is fine because multi-worker is a Postgres
deployment concern.

Because the queue *is* a table, an interrupted job isn't lost: it's still
`running` with a stale `locked_at`, and `reclaim_stale_jobs` puts it back
on the queue at startup. That's the mechanism that finally closes this
project's long-standing "background work doesn't survive a restart" gap,
and the same idea restarts Kafka/MQTT/plugin producers (see
`resume_producers`).

Rows are written through `generator.iter_rows`, so peak memory is one row
no matter how many were asked for — the whole reason jobs exist.
"""

import logging
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import session as db_session
from app.models.entity import Entity
from app.models.job import GenerationJob, JobFormat, JobStatus, Schedule
from app.models.object_storage import ObjectStorageTarget
from app.services import cron
from app.services.generator import build_lookup_pools, iter_rows
from app.services.object_storage import object_key, upload_file
from app.services.row_writers import open_writer, suffix_for

logger = logging.getLogger(__name__)

# How often the running loop updates rows_written, and how often it
# checks for cancellation. Small enough that progress feels live, large
# enough that a big job isn't dominated by UPDATE statements.
CHUNK_ROWS = 500

# A job whose lock is older than this is assumed to belong to a worker
# that died, and is returned to the queue.
STALE_LOCK_MINUTES = 15

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def artifact_dir() -> Path:
    path = Path(settings.JOB_ARTIFACT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------- claiming


def _supports_skip_locked(db: Session) -> bool:
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def claim_next_job(db: Session) -> GenerationJob | None:
    """Take one queued job, or None. Safe to call concurrently."""
    now = datetime.now(UTC).replace(tzinfo=None)

    if _supports_skip_locked(db):
        stmt = (
            select(GenerationJob)
            .where(GenerationJob.status == JobStatus.QUEUED)
            .order_by(GenerationJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = db.execute(stmt).scalars().first()
        if job is None:
            return None
    else:
        # SQLite: no SKIP LOCKED. One worker only — see module docstring.
        job = (
            db.query(GenerationJob)
            .filter(GenerationJob.status == JobStatus.QUEUED)
            .order_by(GenerationJob.created_at)
            .first()
        )
        if job is None:
            return None

    job.status = JobStatus.RUNNING
    job.locked_by = WORKER_ID
    job.locked_at = now
    job.started_at = now
    db.commit()
    db.refresh(job)
    return job


def reclaim_stale_jobs(db: Session) -> int:
    """Return jobs whose worker died back to the queue.

    This is what makes 'survives a restart' true rather than aspirational:
    a job interrupted mid-write is still `running` with an old lock, and
    nothing else would ever move it.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=STALE_LOCK_MINUTES)
    stale = (
        db.query(GenerationJob)
        .filter(GenerationJob.status == JobStatus.RUNNING, GenerationJob.locked_at < cutoff)
        .all()
    )
    for job in stale:
        logger.warning("Reclaiming job %s from worker %s", job.id, job.locked_by)
        job.status = JobStatus.QUEUED
        job.locked_by = None
        job.locked_at = None
        job.started_at = None
        job.rows_written = 0
    if stale:
        db.commit()
    return len(stale)


# -------------------------------------------------------------- writing


class _Cancelled(Exception):
    pass


def _entity_sources(db: Session, job: GenerationJob) -> list[Entity]:
    if job.entity_id is not None:
        entity = db.get(Entity, job.entity_id)
        return [entity] if entity is not None else []
    return db.query(Entity).filter(Entity.project_id == job.project_id).all()


def _row_stream(entity: Entity, count: int):
    return iter_rows(
        entity.fields,
        count,
        fk_pools=build_lookup_pools(entity.lookup_attachments),
        rules=entity.rules,
        workflows=entity.workflows,
        trends=entity.trends,
        error_injections=entity.error_injections,
        event_triggers=entity.event_triggers,
        geo_routes=entity.geo_routes,
    )


def _write_entity(
    db: Session,
    job: GenerationJob,
    entity: Entity,
    path: Path,
    written_so_far: int,
) -> int:
    """Stream one entity's rows to `path`, updating progress as it goes.

    The per-format details live in app.services.row_writers; this loop only
    knows "write a row" and "we are on a boundary", which is what let
    Parquet, ORC and Avro be added without touching the progress and
    cancellation logic.
    """
    written = 0
    writer = open_writer(job.format, path, entity.fields)

    try:
        for row in _row_stream(entity, job.requested_rows):
            writer.write(row)
            written += 1

            if written % CHUNK_ROWS == 0:
                # Checkpoint so a reader (or a crash) sees real rows, then
                # publish progress and honour a cancel request. All three
                # only happen on a chunk boundary: stopping mid-row would
                # leave a malformed file, and for the columnar formats a
                # half-written row group is unreadable rather than merely
                # truncated.
                writer.checkpoint()
                job.rows_written = written_so_far + written
                db.commit()
                db.refresh(job)
                if job.cancel_requested:
                    raise _Cancelled()
    finally:
        # Closed even on cancel: Parquet and ORC keep their footer until
        # close(), and a file without one cannot be opened at all.
        writer.close()

    return written


def run_job(db: Session, job: GenerationJob) -> None:
    """Execute a claimed job to completion, failure or cancellation."""
    directory = artifact_dir() / str(job.id)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = suffix_for(job.format)

    try:
        entities = _entity_sources(db, job)
        if not entities:
            raise ValueError("Nothing to generate — the project has no entities")
        for entity in entities:
            if not entity.fields:
                raise ValueError(f"Entity '{entity.name}' has no fields to generate")

        artifacts: dict[str, Any] = {}
        total = 0
        written_paths: list[tuple[str, Path]] = []
        for entity in entities:
            path = directory / f"{entity.name}.{suffix}"
            written = _write_entity(db, job, entity, path, total)
            total += written
            artifacts[entity.name] = {"file": path.name, "rows": written}
            written_paths.append((entity.name, path))

        # Upload only after every file is written, and only ever *in
        # addition* to the local artifact. A failed upload therefore leaves
        # the generated data on disk to retry rather than losing a run that
        # already did all the expensive work.
        if job.storage_target_id is not None:
            target = db.get(ObjectStorageTarget, job.storage_target_id)
            if target is None:
                raise ValueError("The configured storage target no longer exists")
            for entity_name, path in written_paths:
                key = object_key(target, str(job.id), path.name)
                artifacts[entity_name]["uri"] = upload_file(target, path, key)

        job.rows_written = total
        job.artifacts = artifacts
        job.status = JobStatus.SUCCEEDED

    except _Cancelled:
        job.status = JobStatus.CANCELLED
        job.error = "Cancelled while running"
        logger.info("Job %s cancelled at %s rows", job.id, job.rows_written)

    except Exception as exc:  # noqa: BLE001 - a job must never take the worker down
        job.status = JobStatus.FAILED
        job.error = str(exc)
        logger.warning("Job %s failed: %s", job.id, exc, exc_info=True)

    finally:
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        job.locked_by = None
        job.locked_at = None
        db.commit()


# ------------------------------------------------------------ schedules


def due_schedules(db: Session, now: datetime | None = None) -> list[Schedule]:
    moment = now or datetime.now(UTC).replace(tzinfo=None)
    return (
        db.query(Schedule)
        .filter(
            Schedule.enabled.is_(True),
            Schedule.next_run_at.isnot(None),
            Schedule.next_run_at <= moment,
        )
        .all()
    )


def enqueue_from_schedule(
    db: Session, schedule: Schedule, now: datetime | None = None
) -> GenerationJob:
    """Turn a due schedule into an ordinary queued job.

    A scheduled run is deliberately *just a job*, so it gets the same
    history, progress, cancellation and artifacts as a manual one and
    there's a single execution path to keep correct.
    """
    moment = now or datetime.now(UTC).replace(tzinfo=None)
    job = GenerationJob(
        project_id=schedule.project_id,
        entity_id=schedule.entity_id,
        format=schedule.format,
        requested_rows=schedule.requested_rows,
        schedule_id=schedule.id,
    )
    db.add(job)
    schedule.last_run_at = moment
    schedule.next_run_at = cron.next_after(schedule.cron, moment)
    db.commit()
    db.refresh(job)
    return job


def enqueue_due_schedules(db: Session, now: datetime | None = None) -> int:
    count = 0
    for schedule in due_schedules(db, now):
        try:
            enqueue_from_schedule(db, schedule, now)
            count += 1
        except cron.CronError as exc:
            # Disable rather than retry forever: an unsatisfiable
            # expression will never become satisfiable.
            logger.error("Disabling schedule %s: %s", schedule.id, exc)
            schedule.enabled = False
            db.commit()
    return count


# --------------------------------------------------------------- loop


def tick(db: Session) -> bool:
    """One unit of worker work. Returns True if a job ran, so the caller
    can poll again immediately instead of sleeping."""
    enqueue_due_schedules(db)
    job = claim_next_job(db)
    if job is None:
        return False
    run_job(db, job)
    return True


def worker_pass() -> bool:
    """A tick with its own short-lived session, for the background loop.
    Looks `SessionLocal` up on the module each call so the test suite's
    override reaches it — the same reason websocket_streams does."""
    db = db_session.SessionLocal()
    try:
        return tick(db)
    except SQLAlchemyError:
        logger.warning("Worker pass failed", exc_info=True)
        return False
    finally:
        db.close()


def startup_recovery() -> dict[str, int]:
    """Called once at boot: put interrupted work back on the queue and
    restart background producers that a previous process owned."""
    db = db_session.SessionLocal()
    try:
        reclaimed = reclaim_stale_jobs(db)
        # A schedule created while the process was down may already be
        # overdue; catch those up rather than waiting a full interval.
        enqueued = enqueue_due_schedules(db)
        return {"reclaimed_jobs": reclaimed, "enqueued_schedules": enqueued}
    finally:
        db.close()


def _producers_to_resume() -> dict[str, list]:
    """Read the producer rows that outlived the process.

    Split from starting them because that half is blocking DB work while
    `asyncio.create_task` must run *on* the event loop — calling the
    whole thing in a worker thread raises "no running event loop", which
    is exactly what happened the first time this was wired up.
    """
    from app.models.kafka_output import KafkaOutput
    from app.models.mqtt_output import MQTTOutput
    from app.models.plugin_output import PluginOutput
    from app.services import install
    from app.services.plugins import available_output_plugins

    found: dict[str, list] = {"kafka": [], "mqtt": [], "plugin": []}
    db = db_session.SessionLocal()
    try:
        if install.is_available("kafka"):
            found["kafka"] = db.query(KafkaOutput).all()
        if install.is_available("mqtt"):
            found["mqtt"] = db.query(MQTTOutput).all()

        installed = available_output_plugins()
        for output in db.query(PluginOutput).all():
            if output.plugin_name in installed:
                found["plugin"].append(output)
            else:
                logger.warning(
                    "Not resuming plugin output %s — plugin '%s' is no longer installed",
                    output.id,
                    output.plugin_name,
                )
        # Detach so the rows stay usable after the session closes.
        db.expunge_all()
        return found
    finally:
        db.close()


async def resume_producers() -> dict[str, int]:
    """Restart the background producers described by rows that outlived
    the process — the gap KafkaOutput/MQTTOutput/PluginOutput have
    documented since they were written.

    Async because it creates asyncio tasks; the DB read it needs is
    pushed to a thread so it doesn't block the loop during startup.
    Imports are local because those modules pull in optional broker
    clients (see app.services.install) and this must work on a core-only
    install.
    """
    import asyncio

    from app.services.plugin_output_producers import start_plugin_output
    from app.services.stream_producers import start_kafka_producer, start_mqtt_producer

    found = await asyncio.to_thread(_producers_to_resume)

    started = {"kafka": 0, "mqtt": 0, "plugin": 0}
    for output in found["kafka"]:
        start_kafka_producer(output)
        started["kafka"] += 1
    for output in found["mqtt"]:
        start_mqtt_producer(output)
        started["mqtt"] += 1
    for output in found["plugin"]:
        start_plugin_output(output)
        started["plugin"] += 1

    if any(started.values()):
        logger.info("Resumed background producers: %s", started)
    return started


def create_job(
    db: Session,
    *,
    project_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    requested_rows: int,
    job_format: JobFormat,
    storage_target_id: uuid.UUID | None = None,
) -> GenerationJob:
    job = GenerationJob(
        project_id=project_id,
        entity_id=entity_id,
        requested_rows=requested_rows,
        format=job_format,
        storage_target_id=storage_target_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
