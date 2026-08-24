"""Read sample data from the places generation writes to.

Phases 7 and 9 could only learn from a file someone uploaded through the
browser, while Phase 12 gained the ability to *write* to object storage and
three databases. This closes that asymmetry: the same bucket a job uploads
to, and the same database a push writes into, can be read back as a sample.

Three sources, and one deliberate difference between them:

* **URL** and **S3** produce *bytes*, which go through the existing
  `parse_upload` path — they are files, and pretending otherwise would mean
  a second CSV parser.
* **Database** produces *rows*, and goes straight to `profile_table`. A
  table serialised to CSV and parsed back loses its DATE and DATETIME
  columns to strings, so routing a database through the file path would
  have profiled it *worse* than the same data exported by hand.

Everything here is bounded by `max_rows` before it reaches memory. A
profiling request that happily downloads a 40 GB object is a way to take
the server down, not a feature.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

from app.core.network import UnsafeHostError, ensure_public_host
from app.models.database_connection import DatabaseConnection, DatabaseDialect
from app.models.object_storage import ObjectStorageTarget
from app.services import install
from app.services.db_output import build_engine, validate_identifier
from app.services.object_storage import _client as _s3_client

# Refuse a download larger than this. Generous for a sample, small enough
# that a mistyped key cannot exhaust memory.
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024

FETCH_TIMEOUT_SECONDS = 20

# Only these. `file://` would read the server's own disk and `ftp://` is a
# needless surface — urllib supports both by default, which is exactly the
# kind of thing that turns a fetch feature into an SSRF primitive.
ALLOWED_URL_SCHEMES = ("http", "https")


class IngestError(ValueError):
    pass


def fetch_url(url: str) -> tuple[str, bytes]:
    """Download a sample file over HTTP(S). Returns `(filename, content)`."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise IngestError(
            f"Only {' and '.join(ALLOWED_URL_SCHEMES)} URLs are supported, not '{parsed.scheme}'"
        )
    if not parsed.netloc:
        raise IngestError("That URL has no host")
    if not parsed.hostname:
        raise IngestError("That URL has no host")
    try:
        ensure_public_host(parsed.hostname)
    except UnsafeHostError as exc:
        # Deliberately no more specific than this — confirming *which*
        # private range or that a name resolved at all would help an
        # attacker map the internal network purely from the error text.
        raise IngestError("That URL points at a host this server won't fetch from") from exc

    request = urllib.request.Request(url, headers={"User-Agent": "SynthFlow"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_DOWNLOAD_BYTES:
                raise IngestError(
                    f"That file is {int(declared) // (1024 * 1024)} MB, over the "
                    f"{MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit for a sample"
                )
            # Read one byte past the cap: a server that omits or lies about
            # Content-Length must not be able to stream us out of memory.
            content = response.read(MAX_DOWNLOAD_BYTES + 1)
    except IngestError:
        raise
    except urllib.error.HTTPError as exc:
        raise IngestError(f"HTTP {exc.code} fetching that URL") from exc
    except Exception as exc:
        raise IngestError(f"Could not fetch that URL: {exc}") from exc

    if len(content) > MAX_DOWNLOAD_BYTES:
        raise IngestError(
            f"That file is over the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit for a sample"
        )

    filename = parsed.path.rsplit("/", 1)[-1] or "download.csv"
    return filename, content


def fetch_object(target: ObjectStorageTarget, key: str) -> tuple[str, bytes]:
    """Download one object from a configured storage target."""
    client = _s3_client(target)
    full_key = "/".join(p for p in (target.prefix.strip("/"), key.strip("/")) if p)
    try:
        head = client.head_object(Bucket=target.bucket, Key=full_key)
        size = head.get("ContentLength", 0)
        if size > MAX_DOWNLOAD_BYTES:
            raise IngestError(
                f"That object is {size // (1024 * 1024)} MB, over the "
                f"{MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit for a sample"
            )
        body = client.get_object(Bucket=target.bucket, Key=full_key)["Body"].read()
    except IngestError:
        raise
    except Exception as exc:
        from app.services.object_storage import _readable

        raise IngestError(_readable(exc, f"No object '{full_key}' in that bucket")) from exc

    return full_key.rsplit("/", 1)[-1] or "object.csv", body


def list_objects(target: ObjectStorageTarget, limit: int = 100) -> list[str]:
    """Keys under the target's prefix, so a user can pick one instead of
    having to remember it."""
    client = _s3_client(target)
    prefix = target.prefix.strip("/")
    try:
        response = client.list_objects_v2(
            Bucket=target.bucket, Prefix=f"{prefix}/" if prefix else "", MaxKeys=limit
        )
    except Exception as exc:
        from app.services.object_storage import _readable

        raise IngestError(_readable(exc)) from exc

    keys = [item["Key"] for item in response.get("Contents", [])]
    # Returned relative to the prefix, matching what `fetch_object` expects.
    if prefix:
        keys = [k[len(prefix) + 1 :] for k in keys if k.startswith(prefix + "/")]
    return [k for k in keys if k]


def read_table(
    connection: DatabaseConnection, table: str, max_rows: int
) -> tuple[list[str], list[dict[str, Any]]]:
    """Read up to `max_rows` rows from a table or collection.

    Returns `(columns, rows)` with the driver's native types intact, ready
    for `profiling.profile_table`.
    """
    validate_identifier(table, "table")

    if connection.dialect == DatabaseDialect.MONGODB:
        return _read_collection(connection, table, max_rows)
    return _read_sql_table(connection, table, max_rows)


def _normalise(value: Any) -> Any:
    """Convert driver types the profiler cannot classify.

    A SQL DECIMAL/NUMERIC arrives as `decimal.Decimal`, which is neither an
    int nor a float, so the profiler classified money columns — the single
    most likely thing to be a DECIMAL — as *strings*. Converting to float
    loses exactness, which would matter for arithmetic and does not matter
    here: profiling only ever computes means, deviations and quantiles from
    these values.

    Deliberately narrow. Normalising everything unknown would quietly paper
    over the next type that needs real thought.
    """
    if isinstance(value, Decimal):
        return float(value)
    return value


def _read_sql_table(
    connection: DatabaseConnection, table: str, max_rows: int
) -> tuple[list[str], list[dict[str, Any]]]:
    from sqlalchemy import MetaData, Table, select

    engine = build_engine(connection)
    metadata = MetaData()
    try:
        # Reflect rather than `SELECT *` off a string: the table name has
        # already been validated, but reflection also gives real column
        # names and lets SQLAlchemy do the quoting for the dialect.
        reflected = Table(table, metadata, autoload_with=engine)
        with engine.connect() as conn:
            result = conn.execute(select(reflected).limit(max_rows))
            columns = list(result.keys())
            rows = [{c: _normalise(v) for c, v in zip(columns, row, strict=True)} for row in result]
    except Exception as exc:
        raise IngestError(_sql_reason(exc, table)) from exc

    if not rows:
        raise IngestError(f"Table '{table}' has no rows to learn from")
    return columns, rows


def _sql_reason(exc: Exception, table: str) -> str:
    text = str(getattr(exc, "orig", None) or exc)
    if "does not exist" in text or "doesn't exist" in text or "no such table" in text.lower():
        return f"Table '{table}' does not exist on that connection"
    return text


def _read_collection(
    connection: DatabaseConnection, collection: str, max_rows: int
) -> tuple[list[str], list[dict[str, Any]]]:
    install.require("mongo")
    from app.services.db_output import _mongo_client

    client = _mongo_client(connection)
    try:
        # `_id` is excluded: it is MongoDB's own key, present in every
        # document, and profiling it would add a meaningless high-cardinality
        # string column to every learned project.
        documents = list(
            client[connection.database][collection].find({}, {"_id": 0}).limit(max_rows)
        )
    except Exception as exc:
        raise IngestError(str(exc)) from exc
    finally:
        client.close()

    if not documents:
        raise IngestError(f"Collection '{collection}' has no documents to learn from")

    # Documents need not share a shape, so the column set is the union in
    # first-seen order — a field missing from a document reads as null,
    # which is exactly what the profiler should see.
    columns: list[str] = []
    seen: set[str] = set()
    for document in documents:
        for key in document:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns, documents
