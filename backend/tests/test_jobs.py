"""Phase 8: streaming generation, the job queue, and schedules.

The worker is off in tests (see conftest), so these drive it explicitly
via `jobs.tick()`. That's deliberate — it means every assertion here is
about a deterministic step rather than a race with a background loop.
"""

import csv
import json
from datetime import datetime, timedelta

import pytest

from app.db import session as db_session
from app.models.field import EntityField, FieldType
from app.models.job import GenerationJob, JobStatus
from app.services import cron, jobs
from app.services.generator import generate_rows, iter_rows


def _fields() -> list[EntityField]:
    return [
        EntityField(
            name="id", field_type=FieldType.INTEGER, order=0, required=True, nullable=False
        ),
        EntityField(
            name="name", field_type=FieldType.STRING, order=1, required=True, nullable=False
        ),
    ]


def _project(client, headers, name="Jobs"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _entity(client, headers, project_id, name="Row"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "value", "field_type": "integer", "required": True, "nullable": False},
        headers=headers,
    )
    return entity["id"]


def _drain(limit: int = 10) -> int:
    """Run the worker until the queue is empty, using the same session
    factory the tests patched."""
    db = db_session.SessionLocal()
    try:
        ran = 0
        for _ in range(limit):
            if not jobs.tick(db):
                break
            ran += 1
        return ran
    finally:
        db.close()


# ------------------------------------------------------- streaming


def test_iter_rows_matches_generate_rows():
    """The streaming refactor must not have changed behaviour."""
    fields = _fields()
    streamed = list(iter_rows(fields, 25))
    listed = generate_rows(fields, 25)
    assert len(streamed) == len(listed) == 25
    assert set(streamed[0]) == set(listed[0])


def test_iter_rows_is_lazy():
    """It must not have generated everything before yielding the first
    row — that's the whole point."""
    stream = iter_rows(_fields(), 1_000_000)
    first = next(stream)
    assert "id" in first
    stream.close()


def test_iter_rows_memory_does_not_grow_with_count():
    import tracemalloc

    def peak(count: int) -> int:
        tracemalloc.start()
        for _ in iter_rows(_fields(), count):
            pass
        used = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return used

    small, large = peak(1_000), peak(20_000)
    # 20x the rows must not mean anything like 20x the memory.
    assert large < small * 3


# ------------------------------------------------------------ cron


@pytest.mark.parametrize(
    ("expression", "after", "expected"),
    [
        ("* * * * *", datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 10, 1)),
        ("30 2 * * *", datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 2, 2, 30)),
        ("0 */6 * * *", datetime(2026, 1, 1, 1, 0), datetime(2026, 1, 1, 6, 0)),
        ("0 0 1 * *", datetime(2026, 1, 15, 0, 0), datetime(2026, 2, 1, 0, 0)),
        # Sunday is 0 in cron; 2026-01-04 is a Sunday.
        ("0 9 * * 0", datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 4, 9, 0)),
        ("15,45 * * * *", datetime(2026, 1, 1, 10, 20), datetime(2026, 1, 1, 10, 45)),
    ],
)
def test_cron_next_after(expression, after, expected):
    assert cron.next_after(expression, after) == expected


@pytest.mark.parametrize(
    "expression",
    ["* * * *", "60 * * * *", "* 24 * * *", "abc * * * *", "5-1 * * * *", "* * * * 9"],
)
def test_cron_rejects_bad_expressions(expression):
    with pytest.raises(cron.CronError):
        cron.parse(expression)


def test_cron_rejects_a_date_that_never_comes():
    """Better to refuse than to create a schedule that silently never
    fires."""
    with pytest.raises(cron.CronError):
        cron.next_after("0 0 31 2 *", datetime(2026, 1, 1))


def test_cron_describe_is_human_readable():
    assert cron.describe("30 2 * * *") == "Daily at 02:30 UTC"
    assert "Sunday" in cron.describe("0 9 * * 0")
    assert cron.describe("* * * * *") == "Every minute"


# ------------------------------------------------------------- jobs


def test_creating_a_job_queues_it_without_running_it(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 50},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["rows_written"] == 0
    assert body["started_at"] is None


def test_a_job_runs_and_writes_a_downloadable_artifact(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 1200},
        headers=auth_headers,
    ).json()

    assert _drain() == 1

    done = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}", headers=auth_headers
    ).json()
    assert done["status"] == "succeeded"
    assert done["rows_written"] == 1200
    assert done["finished_at"] is not None
    assert "Row" in done["artifacts"]

    download = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}/artifacts/Row",
        headers=auth_headers,
    )
    assert download.status_code == 200
    rows = list(csv.DictReader(download.text.splitlines()))
    assert len(rows) == 1200
    assert set(rows[0]) == {"value"}


def test_jsonl_format_writes_one_object_per_line(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 10, "format": "jsonl"},
        headers=auth_headers,
    ).json()
    _drain()

    download = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}/artifacts/Row", headers=auth_headers
    )
    lines = [ln for ln in download.text.splitlines() if ln.strip()]
    assert len(lines) == 10
    assert json.loads(lines[0])["value"] is not None


def test_a_whole_project_job_writes_one_artifact_per_entity(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id, name="A")
    _entity(client, auth_headers, project_id, name="B")

    job = client.post(
        f"/api/v1/projects/{project_id}/jobs", json={"rows": 5}, headers=auth_headers
    ).json()
    _drain()

    done = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}", headers=auth_headers
    ).json()
    assert done["status"] == "succeeded"
    assert set(done["artifacts"]) == {"A", "B"}
    assert done["rows_written"] == 10


def test_a_job_exceeding_the_interactive_row_cap_still_runs(client, auth_headers):
    """MAX_GENERATE_ROWS caps one in-memory response; a job streams to
    disk, so it must be allowed past that ceiling."""
    from app.core.config import settings

    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    rows = settings.MAX_GENERATE_ROWS + 2000

    # The interactive route refuses.
    refused = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": rows},
        headers=auth_headers,
    )
    assert refused.status_code == 400

    # A job does not.
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": rows},
        headers=auth_headers,
    ).json()
    _drain()
    done = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}", headers=auth_headers
    ).json()
    assert done["status"] == "succeeded"
    assert done["rows_written"] == rows


def test_a_failing_job_is_recorded_not_raised(client, auth_headers):
    project_id = _project(client, auth_headers)
    # An entity with no fields can't generate.
    empty = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()

    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": empty["id"], "rows": 5},
        headers=auth_headers,
    ).json()
    _drain()

    done = client.get(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}", headers=auth_headers
    ).json()
    assert done["status"] == "failed"
    assert "no fields" in done["error"]


def test_cancelling_a_queued_job_stops_it_running(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 100},
        headers=auth_headers,
    ).json()

    cancelled = client.post(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}/cancel", headers=auth_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # Nothing left for the worker to pick up.
    assert _drain() == 0


def test_cancelling_a_finished_job_is_rejected(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    ).json()
    _drain()

    resp = client.post(
        f"/api/v1/projects/{project_id}/jobs/{job['id']}/cancel", headers=auth_headers
    )
    assert resp.status_code == 400


def test_claiming_marks_the_job_and_records_the_worker(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    )

    db = db_session.SessionLocal()
    try:
        claimed = jobs.claim_next_job(db)
        assert claimed is not None
        assert claimed.status == JobStatus.RUNNING
        assert claimed.locked_by == jobs.WORKER_ID
        assert claimed.locked_at is not None
        # A second worker must not get the same job.
        assert jobs.claim_next_job(db) is None
    finally:
        db.close()


def test_an_interrupted_job_is_reclaimed_rather_than_lost(client, auth_headers):
    """The restart story: a job whose worker died is still 'running' with
    a stale lock, and nothing else would ever move it."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    )

    db = db_session.SessionLocal()
    try:
        claimed = jobs.claim_next_job(db)
        # Simulate the worker dying long ago.
        claimed.locked_at = datetime.utcnow() - timedelta(minutes=jobs.STALE_LOCK_MINUTES + 5)
        claimed.rows_written = 3
        db.commit()

        assert jobs.reclaim_stale_jobs(db) == 1
        db.refresh(claimed)
        assert claimed.status == JobStatus.QUEUED
        assert claimed.locked_by is None
        # Progress resets so the rerun doesn't double-count.
        assert claimed.rows_written == 0
    finally:
        db.close()

    assert _drain() == 1


def test_a_fresh_lock_is_not_reclaimed(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    )
    db = db_session.SessionLocal()
    try:
        jobs.claim_next_job(db)
        assert jobs.reclaim_stale_jobs(db) == 0
    finally:
        db.close()


def test_jobs_are_scoped_to_their_project(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    job = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    ).json()

    other = _project(client, auth_headers, name="Other")
    resp = client.get(f"/api/v1/projects/{other}/jobs/{job['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_job_routes_require_auth(client, auth_headers):
    project_id = _project(client, auth_headers)
    assert client.get(f"/api/v1/projects/{project_id}/jobs").status_code == 401
    assert client.post(f"/api/v1/projects/{project_id}/jobs", json={"rows": 1}).status_code == 401


def test_job_rejects_an_entity_from_another_project(client, auth_headers):
    a = _project(client, auth_headers, name="A")
    b = _project(client, auth_headers, name="B")
    entity_id = _entity(client, auth_headers, b)

    resp = client.post(
        f"/api/v1/projects/{a}/jobs",
        json={"entity_id": entity_id, "rows": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# -------------------------------------------------------- schedules


def test_creating_a_schedule_computes_its_next_run(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "nightly", "cron": "0 2 * * *", "rows": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["next_run_at"] is not None
    assert body["description"] == "Daily at 02:00 UTC"


def test_a_bad_cron_expression_is_rejected_at_creation(client, auth_headers):
    project_id = _project(client, auth_headers)
    resp = client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "bad", "cron": "not a cron", "rows": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_a_due_schedule_enqueues_an_ordinary_job(client, auth_headers):
    """A scheduled run is deliberately just a job, so it gets the same
    history, progress and artifacts as a manual one."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "nightly", "cron": "* * * * *", "rows": 20, "entity_id": entity_id},
        headers=auth_headers,
    )

    db = db_session.SessionLocal()
    try:
        # Nothing due yet — next_run_at is in the future.
        assert jobs.enqueue_due_schedules(db) == 0
        # Pretend a minute passed.
        assert jobs.enqueue_due_schedules(db, datetime.utcnow() + timedelta(minutes=2)) == 1
        queued = db.query(GenerationJob).all()
        assert len(queued) == 1
        assert queued[0].schedule_id is not None
    finally:
        db.close()

    _drain()
    listed = client.get(f"/api/v1/projects/{project_id}/jobs", headers=auth_headers).json()
    assert listed[0]["status"] == "succeeded"
    assert listed[0]["schedule_id"] is not None


def test_running_a_schedule_advances_its_next_run(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "hourly", "cron": "0 * * * *", "rows": 5},
        headers=auth_headers,
    )

    db = db_session.SessionLocal()
    try:
        jobs.enqueue_due_schedules(db, datetime.utcnow() + timedelta(days=1))
    finally:
        db.close()

    after = client.get(f"/api/v1/projects/{project_id}/schedules", headers=auth_headers).json()[0]
    assert after["last_run_at"] is not None
    assert after["next_run_at"] is not None


def test_a_disabled_schedule_does_not_fire(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "off", "cron": "* * * * *", "rows": 5, "enabled": False},
        headers=auth_headers,
    )

    db = db_session.SessionLocal()
    try:
        assert jobs.enqueue_due_schedules(db, datetime.utcnow() + timedelta(days=1)) == 0
    finally:
        db.close()


def test_deleting_a_schedule(client, auth_headers):
    project_id = _project(client, auth_headers)
    created = client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"name": "x", "cron": "0 2 * * *", "rows": 5},
        headers=auth_headers,
    ).json()

    assert (
        client.delete(
            f"/api/v1/projects/{project_id}/schedules/{created['id']}", headers=auth_headers
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/projects/{project_id}/schedules", headers=auth_headers).json() == []
