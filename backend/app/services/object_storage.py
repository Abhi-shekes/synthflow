"""Upload generated files to S3-compatible object storage.

One connector for AWS S3, MinIO, Cloudflare R2, Backblaze B2 and
DigitalOcean Spaces, because they all speak the same API and differ only in
`endpoint_url`. Writing five vendor connectors that each wrap boto3 would
have been five things to keep working.

Uploads happen *after* a job has finished writing its file, not instead of
writing it. Two reasons: the local artifact stays downloadable exactly as
before, so nothing regresses for anyone not using this; and streaming
straight to object storage would mean a failed upload loses the generated
data entirely, whereas this leaves it on disk to retry.

Credentials come from the target row — never from ambient environment
variables or an instance profile. Picking up whatever credentials the host
happens to have is convenient right up until a misconfigured target
silently writes into the wrong account.
"""

from __future__ import annotations

from pathlib import Path

from app.models.object_storage import ObjectStorageTarget
from app.services import install


class ObjectStorageError(ValueError):
    pass


def _client(target: ObjectStorageTarget):
    """A boto3 S3 client. Imported inside the function because boto3 is an
    optional extra and the core install must import this module without
    it — same reasoning as the Kafka producer and the Mongo client."""
    install.require("s3")
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=target.region or "us-east-1",
        endpoint_url=target.endpoint_url or None,
        aws_access_key_id=target.access_key_id,
        aws_secret_access_key=target.secret_access_key,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def object_key(target: ObjectStorageTarget, *parts: str) -> str:
    """Join a target's prefix with path parts into an S3 key.

    Keys use forward slashes on every platform, so this deliberately does
    not use `os.path.join` — a Windows host would otherwise produce
    backslashes in a key and create objects nobody can find.
    """
    pieces = [p.strip("/") for p in (target.prefix, *parts) if p and p.strip("/")]
    return "/".join(pieces)


def uri_for(target: ObjectStorageTarget, key: str) -> str:
    return f"s3://{target.bucket}/{key}"


def test_connection(target: ObjectStorageTarget) -> tuple[bool, str]:
    """Check the bucket is reachable and the credentials work.

    `head_bucket` rather than `list_buckets`: listing requires an
    account-level permission that a correctly-scoped key often won't have,
    so it would report failure for a target that works perfectly well for
    uploading.
    """
    try:
        client = _client(target)
        client.head_bucket(Bucket=target.bucket)
        return True, "Bucket is reachable"
    except ObjectStorageError as exc:
        return False, str(exc)
    except Exception as exc:  # botocore raises its own hierarchy
        return False, _readable(exc)


def _readable(exc: Exception) -> str:
    """botocore's ClientError stringifies to a wall of request metadata.
    Pull out the bit that tells someone what to fix."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error", {})
        code = error.get("Code")
        message = error.get("Message")
        if code == "404" or code == "NoSuchBucket":
            return "Bucket does not exist"
        if code in ("403", "AccessDenied"):
            return "Access denied — check the key, secret and bucket permissions"
        if code and message:
            return f"{code}: {message}"
    return str(exc)


def upload_file(target: ObjectStorageTarget, path: Path, key: str) -> str:
    """Upload one file and return its `s3://` URI.

    `upload_file` (not `put_object`) because it handles multipart for large
    files by itself — a 5 GB generation artifact would exceed the
    single-request limit, and a job that can write that much should be able
    to upload it.
    """
    try:
        client = _client(target)
        client.upload_file(str(path), target.bucket, key)
    except ObjectStorageError:
        raise
    except Exception as exc:
        raise ObjectStorageError(_readable(exc)) from exc
    return uri_for(target, key)
