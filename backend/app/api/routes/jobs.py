import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.entity import Entity
from app.models.job import GenerationJob, JobFormat, JobStatus, Schedule
from app.models.user import User
from app.services import cron, jobs

router = APIRouter(prefix="/projects/{project_id}", tags=["jobs"])


class JobCreate(BaseModel):
    entity_id: uuid.UUID | None = None
    rows: int = Field(gt=0)
    format: JobFormat = JobFormat.CSV
    # Optional upload destination. Null keeps the artifact on disk only,
    # which stays the default — see app.services.object_storage.
    storage_target_id: uuid.UUID | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    entity_id: uuid.UUID | None
    status: JobStatus
    format: JobFormat
    requested_rows: int
    rows_written: int
    artifacts: dict | None
    error: str | None
    schedule_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ScheduleCreate(BaseModel):
    name: str
    cron: str
    entity_id: uuid.UUID | None = None
    rows: int = Field(gt=0)
    format: JobFormat = JobFormat.CSV
    enabled: bool = True


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    entity_id: uuid.UUID | None
    name: str
    cron: str
    format: JobFormat
    requested_rows: int
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime


class ScheduleReadWithSummary(ScheduleRead):
    description: str


def _get_owned_job(
    project_id: uuid.UUID, job_id: uuid.UUID, user: User, db: Session
) -> GenerationJob:
    _get_owned_project(project_id, user, db)
    job = db.get(GenerationJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _check_entity(project_id: uuid.UUID, entity_id: uuid.UUID | None, db: Session) -> None:
    if entity_id is None:
        return
    entity = db.get(Entity, entity_id)
    if entity is None or entity.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_id does not belong to this project",
        )


# ----------------------------------------------------------------- jobs


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    project_id: uuid.UUID,
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJob:
    """Queue a generation run.

    Unlike `POST .../generate`, this returns immediately and the rows are
    streamed to a file by a worker — which is why `rows` is bounded by
    MAX_JOB_ROWS (disk and patience) rather than MAX_GENERATE_ROWS (one
    in-memory HTTP response).
    """
    _get_owned_project(project_id, current_user, db)
    _check_entity(project_id, payload.entity_id, db)

    if payload.rows > settings.MAX_JOB_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rows must be at most {settings.MAX_JOB_ROWS}",
        )

    return jobs.create_job(
        db,
        project_id=project_id,
        entity_id=payload.entity_id,
        requested_rows=payload.rows,
        job_format=payload.format,
        storage_target_id=payload.storage_target_id,
    )


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    project_id: uuid.UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GenerationJob]:
    _get_owned_project(project_id, current_user, db)
    return (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project_id)
        .order_by(GenerationJob.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJob:
    return _get_owned_job(project_id, job_id, current_user, db)


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJob:
    """Cancellation is cooperative for a running job: the flag is set here
    and the streaming loop stops at the next chunk boundary, so the
    partial file is never left mid-row. A job that hasn't started yet is
    cancelled outright."""
    job = _get_owned_job(project_id, job_id, current_user, db)

    if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is already {job.status}",
        )

    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.CANCELLED
        job.error = "Cancelled before it started"
        job.finished_at = datetime.utcnow()
    else:
        job.cancel_requested = True

    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/artifacts/{name}")
def download_artifact(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = _get_owned_job(project_id, job_id, current_user, db)
    if not job.artifacts or name not in job.artifacts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such artifact")

    filename = job.artifacts[name]["file"]
    directory = (jobs.artifact_dir() / str(job.id)).resolve()
    path = (directory / filename).resolve()
    # The filename comes from the job's own artifacts map rather than the
    # URL, but resolve-and-check anyway so a crafted stored value can't
    # escape the job's directory.
    if not path.is_file() or directory not in path.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is gone")

    return FileResponse(
        Path(path),
        media_type="text/csv" if job.format == JobFormat.CSV else "application/x-ndjson",
        filename=filename,
    )


# ------------------------------------------------------------ schedules


@router.post(
    "/schedules", response_model=ScheduleReadWithSummary, status_code=status.HTTP_201_CREATED
)
def create_schedule(
    project_id: uuid.UUID,
    payload: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleReadWithSummary:
    _get_owned_project(project_id, current_user, db)
    _check_entity(project_id, payload.entity_id, db)

    if payload.rows > settings.MAX_JOB_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rows must be at most {settings.MAX_JOB_ROWS}",
        )

    # Validate up front: a schedule that silently never fires is a worse
    # failure than one that refuses to be created.
    try:
        next_run = cron.next_after(payload.cron, datetime.utcnow())
    except cron.CronError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    schedule = Schedule(
        project_id=project_id,
        entity_id=payload.entity_id,
        name=payload.name,
        cron=payload.cron,
        format=payload.format,
        requested_rows=payload.rows,
        enabled=payload.enabled,
        next_run_at=next_run,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return ScheduleReadWithSummary(
        **ScheduleRead.model_validate(schedule).model_dump(),
        description=cron.describe(schedule.cron),
    )


@router.get("/schedules", response_model=list[ScheduleReadWithSummary])
def list_schedules(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScheduleReadWithSummary]:
    _get_owned_project(project_id, current_user, db)
    rows = (
        db.query(Schedule)
        .filter(Schedule.project_id == project_id)
        .order_by(Schedule.created_at)
        .all()
    )
    return [
        ScheduleReadWithSummary(
            **ScheduleRead.model_validate(s).model_dump(), description=cron.describe(s.cron)
        )
        for s in rows
    ]


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
