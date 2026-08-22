"""Phase 12 — object storage targets.

Key construction, credential handling and error translation are covered
here; actual uploads are verified live against a real MinIO via the `s3`
compose profile, the same split the broker and database connectors use.
"""

from types import SimpleNamespace

import pytest

from app.models.object_storage import StorageProvider
from app.services import install, object_storage

TARGET_PAYLOAD = {
    "name": "archive",
    "bucket": "synthflow-artifacts",
    "prefix": "runs",
    "region": "eu-west-1",
    "endpoint_url": "http://minio:9000",
    "access_key_id": "key",
    "secret_access_key": "secret",
}


def target(**overrides):
    base = dict(
        provider=StorageProvider.S3,
        bucket="bucket",
        prefix="",
        region="us-east-1",
        endpoint_url="",
        access_key_id="key",
        secret_access_key="secret",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _create_project(client, headers, name="Storage"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


# --------------------------------------------------------------------------
# Key construction
# --------------------------------------------------------------------------


def test_prefix_and_parts_join_into_one_key():
    assert object_storage.object_key(target(prefix="runs"), "job-1", "out.parquet") == (
        "runs/job-1/out.parquet"
    )


def test_an_empty_prefix_means_the_bucket_root():
    assert object_storage.object_key(target(prefix=""), "job-1", "out.csv") == "job-1/out.csv"


def test_stray_slashes_never_produce_an_empty_path_segment():
    """`runs//job-1/out.csv` is a different, and confusing, object from
    `runs/job-1/out.csv` — S3 does not normalise it away."""
    key = object_storage.object_key(target(prefix="/runs/"), "/job-1/", "out.csv")
    assert key == "runs/job-1/out.csv"
    assert "//" not in key


def test_a_uri_is_built_from_bucket_and_key():
    assert object_storage.uri_for(target(bucket="b"), "k/v.csv") == "s3://b/k/v.csv"


# --------------------------------------------------------------------------
# Error translation
# --------------------------------------------------------------------------


def test_a_missing_bucket_says_so_rather_than_dumping_request_metadata():
    """botocore's ClientError stringifies to a wall of request ids. The
    person reading it needs to know what to fix."""
    error = Exception()
    error.response = {"Error": {"Code": "404", "Message": "Not Found"}}
    assert object_storage._readable(error) == "Bucket does not exist"


def test_access_denied_points_at_the_credentials():
    error = Exception()
    error.response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
    assert "check the key" in object_storage._readable(error)


def test_an_unrecognised_error_still_carries_its_code_and_message():
    error = Exception()
    error.response = {"Error": {"Code": "SlowDown", "Message": "Reduce your request rate"}}
    assert object_storage._readable(error) == "SlowDown: Reduce your request rate"


def test_a_non_botocore_exception_falls_back_to_its_own_text():
    assert "boom" in object_storage._readable(RuntimeError("boom"))


# --------------------------------------------------------------------------
# Optional extra
# --------------------------------------------------------------------------


def test_the_module_imports_without_boto3():
    """Guards the core leg of the CI matrix — a module-scope `import boto3`
    would break every install that never uploads anything."""
    assert hasattr(object_storage, "upload_file")


@pytest.mark.skipif(install.is_available("s3"), reason="only meaningful without the 's3' extra")
def test_a_missing_driver_names_the_extra_to_install():
    ok, detail = object_storage.test_connection(target())
    assert ok is False
    assert "s3" in detail.lower()


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def test_creating_a_target_never_returns_the_secret(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    response = client.post(
        f"/api/v1/projects/{project_id}/storage-targets",
        json=TARGET_PAYLOAD,
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "secret_access_key" not in body
    assert body["bucket"] == "synthflow-artifacts"
    # The key id is not a secret and is genuinely useful for telling two
    # targets apart, so unlike the secret it is returned.
    assert body["access_key_id"] == "key"


def test_listing_targets_never_returns_the_secret(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    client.post(
        f"/api/v1/projects/{project_id}/storage-targets",
        json=TARGET_PAYLOAD,
        headers=auth_headers,
    )
    listed = client.get(
        f"/api/v1/projects/{project_id}/storage-targets", headers=auth_headers
    ).json()
    assert len(listed) == 1
    assert "secret_access_key" not in listed[0]


def test_the_secret_is_encrypted_in_the_database(client, auth_headers):
    """Reuses Phase 10's EncryptedString, so this proves the column type is
    actually applied rather than that encryption works in the abstract.

    Reads through raw SQL on purpose: going via the ORM would decrypt on
    the way out and prove nothing about what is on disk.
    """
    from sqlalchemy import text

    from app.core.secrets import is_encrypted
    from app.db import session as db_session

    project_id = _create_project(client, auth_headers)
    client.post(
        f"/api/v1/projects/{project_id}/storage-targets",
        json=TARGET_PAYLOAD,
        headers=auth_headers,
    )
    db = db_session.SessionLocal()
    try:
        stored = db.execute(text("SELECT secret_access_key FROM object_storage_targets")).scalar()
    finally:
        db.close()
    assert is_encrypted(stored)
    assert "secret" not in stored


def test_targets_are_scoped_per_project(client, auth_headers):
    first = _create_project(client, auth_headers, "One")
    second = _create_project(client, auth_headers, "Two")
    client.post(
        f"/api/v1/projects/{first}/storage-targets", json=TARGET_PAYLOAD, headers=auth_headers
    )
    listed = client.get(f"/api/v1/projects/{second}/storage-targets", headers=auth_headers).json()
    assert listed == []


def test_deleting_a_target(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    created = client.post(
        f"/api/v1/projects/{project_id}/storage-targets",
        json=TARGET_PAYLOAD,
        headers=auth_headers,
    ).json()
    assert (
        client.delete(
            f"/api/v1/projects/{project_id}/storage-targets/{created['id']}",
            headers=auth_headers,
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/projects/{project_id}/storage-targets", headers=auth_headers).json()
        == []
    )


def test_a_target_from_another_project_is_not_reachable(client, auth_headers):
    first = _create_project(client, auth_headers, "One")
    second = _create_project(client, auth_headers, "Two")
    created = client.post(
        f"/api/v1/projects/{first}/storage-targets", json=TARGET_PAYLOAD, headers=auth_headers
    ).json()
    response = client.delete(
        f"/api/v1/projects/{second}/storage-targets/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 404


def test_a_job_can_be_queued_without_a_storage_target(client, auth_headers):
    """Uploading is opt-in; the default must stay "leave it on disk" so
    nothing changes for anyone not using object storage."""
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Row"}, headers=auth_headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/jobs",
        json={"entity_id": entity["id"], "rows": 5},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
