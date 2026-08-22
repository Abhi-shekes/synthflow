"""Phase 12 — input connectors.

Profiling can now read from the same places generation writes to: a URL, an
object-storage key, or a database table. The network-touching halves are
verified live against real MinIO, MySQL and MongoDB; what is here is the
logic that decides *whether to make the request at all*, plus the type
handling that a live test would only catch by accident.
"""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import ingest
from app.services.profiling.profile import ProfileError, profile_table, profile_tables

# --------------------------------------------------------------------------
# URL fetching — what it refuses
# --------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/data.csv"])
def test_only_http_urls_are_allowed(url):
    """urllib supports file:// and ftp:// out of the box, which would turn
    "profile from a URL" into a way to read the server's own disk. The
    scheme check is the whole difference between a feature and an SSRF
    primitive."""
    with pytest.raises(ingest.IngestError) as exc:
        ingest.fetch_url(url)
    assert "http" in str(exc.value)


def test_a_url_without_a_host_is_rejected():
    with pytest.raises(ingest.IngestError):
        ingest.fetch_url("http:///no-host.csv")


def test_a_declared_oversize_download_is_refused_before_reading_it(monkeypatch):
    """Refused on Content-Length, so a huge file costs one request rather
    than its own size in memory."""

    class FakeResponse:
        headers = {"Content-Length": str(ingest.MAX_DOWNLOAD_BYTES + 1)}

        def read(self, *_):  # pragma: no cover - must not be reached
            raise AssertionError("body should never be read")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(ingest.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    with pytest.raises(ingest.IngestError) as exc:
        ingest.fetch_url("http://example.com/big.csv")
    assert "limit" in str(exc.value)


def test_a_server_that_lies_about_its_size_is_still_capped(monkeypatch):
    """A missing or dishonest Content-Length must not let a server stream
    us out of memory, which is why the read is bounded too."""

    class FakeResponse:
        headers = {}

        def read(self, n):
            return b"x" * n

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(ingest.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    with pytest.raises(ingest.IngestError) as exc:
        ingest.fetch_url("http://example.com/lying.csv")
    assert "limit" in str(exc.value)


def test_a_filename_is_derived_from_the_url_path(monkeypatch):
    """The profiler names an entity after the file, so a URL ending in
    /customers.csv must not produce an entity called "download"."""

    class FakeResponse:
        headers = {"Content-Length": "3"}

        def read(self, *_):
            return b"a,b"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(ingest.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    name, _ = ingest.fetch_url("http://example.com/data/customers.csv")
    assert name == "customers.csv"


# --------------------------------------------------------------------------
# Type handling
# --------------------------------------------------------------------------


def test_a_decimal_becomes_a_float():
    """Regression: SQL DECIMAL arrives as decimal.Decimal, which is neither
    int nor float, so the profiler classified money columns — the most
    likely thing to *be* a DECIMAL — as strings."""
    assert ingest._normalise(Decimal("12.50")) == 12.5
    assert isinstance(ingest._normalise(Decimal("12.50")), float)


def test_other_types_are_left_alone():
    """Normalising everything unknown would paper over the next type that
    needs real thought."""
    when = datetime(2024, 3, 5, 10, 30)
    assert ingest._normalise(when) is when
    assert ingest._normalise("text") == "text"
    assert ingest._normalise(None) is None


def test_database_dates_keep_their_type_through_profiling():
    """The reason `profile_table` was split out of `profile_file`. A CSV
    round-trip turns these into strings, so a database would have profiled
    *worse* than the same data exported by hand."""
    rows = [
        {"id": i, "joined": date(2024, 3, i + 1), "seen": datetime(2024, 3, i + 1, 10, 0)}
        for i in range(1, 6)
    ]
    entity, _, _ = profile_table("dated", ["id", "joined", "seen"], rows)
    types = {f.name: f.field_type for f in entity.fields}
    assert types["joined"] == "date"
    assert types["seen"] == "datetime"


def test_profiling_a_table_with_no_columns_is_an_error():
    with pytest.raises(ProfileError):
        profile_table("empty", [], [])


def test_profiling_nothing_is_an_error():
    with pytest.raises(ProfileError):
        profile_tables([])


def test_several_tables_are_profiled_into_one_project():
    """Multi-table is what makes relationship detection possible at all —
    the same reason the file endpoint takes several files."""
    customers = [{"cid": i, "age": 30 + i} for i in range(1, 40)]
    orders = [{"oid": i, "cid": (i % 39) + 1} for i in range(1, 60)]
    result, profiles = profile_tables(
        [("customers", ["cid", "age"], customers), ("orders", ["oid", "cid"], orders)]
    )
    assert {e.name for e in result.template.entities} == {"customers", "orders"}
    assert set(profiles) == {"customers", "orders"}


def test_the_description_names_the_kind_of_source():
    """ "Learned from 2 tables" and "learned from 2 sample files" are
    different provenance, and the project description is where someone
    looks to remember which."""
    result, _ = profile_tables([("t", ["a"], [{"a": 1}])], source_label="table")
    assert "table" in result.template.description


# --------------------------------------------------------------------------
# API validation
# --------------------------------------------------------------------------


def _project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Sources"}, headers=headers).json()["id"]


def test_exactly_one_kind_of_source_is_required(client, auth_headers):
    project_id = _project(client, auth_headers)
    for payload in (
        {"project_id": project_id},
        {"project_id": project_id, "urls": ["http://a/b.csv"], "tables": ["t"]},
    ):
        response = client.post("/api/v1/profile/from-source", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "exactly one" in response.json()["detail"]


def test_object_keys_need_a_storage_target(client, auth_headers):
    project_id = _project(client, auth_headers)
    response = client.post(
        "/api/v1/profile/from-source",
        json={"project_id": project_id, "object_keys": ["a.csv"]},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "storage_target_id" in response.json()["detail"]


def test_tables_need_a_connection(client, auth_headers):
    project_id = _project(client, auth_headers)
    response = client.post(
        "/api/v1/profile/from-source",
        json={"project_id": project_id, "tables": ["customers"]},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "connection_id" in response.json()["detail"]


def test_a_project_you_do_not_own_is_not_readable(client, auth_headers):
    import uuid

    response = client.post(
        "/api/v1/profile/from-source",
        json={"project_id": str(uuid.uuid4()), "urls": ["http://example.com/a.csv"]},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_a_url_needs_no_project_at_all(client, auth_headers):
    """A public URL needs no credentials, and requiring a project for it
    would mean you could not learn from one until you had already created a
    project to learn into. The 400 here is the unreachable host, which is
    proof the request got past validation."""
    response = client.post(
        "/api/v1/profile/from-source",
        json={"urls": ["http://127.0.0.1:9/nothing.csv"]},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "project" not in response.json()["detail"].lower()


def test_a_table_name_that_is_not_an_identifier_is_refused():
    connection = SimpleNamespace(dialect="postgresql")
    with pytest.raises(ValueError):
        ingest.read_table(connection, "users; DROP TABLE users", 100)
