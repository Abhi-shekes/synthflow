"""Phase 12 — columnar and row-binary job formats.

Each format is written and then read back with the *reading* side of its
own library, not by inspecting what we just wrote. A test that only checks
"the file is non-empty" would have passed for the ORC zero-row bug, which
produced a file too short to open.
"""

from types import SimpleNamespace

import pytest

from app.models.field import FieldType
from app.models.job import JobFormat
from app.services import install
from app.services.row_writers import BUFFER_ROWS, open_writer, suffix_for

requires_parquet = pytest.mark.skipif(
    not install.is_available("parquet"),
    reason="optional 'parquet' extra is not installed in this environment",
)
requires_avro = pytest.mark.skipif(
    not install.is_available("avro"),
    reason="optional 'avro' extra is not installed in this environment",
)


def field(name, field_type=FieldType.STRING):
    return SimpleNamespace(name=name, field_type=field_type, preset=None)


FIELDS = [
    field("id", FieldType.INTEGER),
    field("label", FieldType.STRING),
    field("amount", FieldType.FLOAT),
    field("active", FieldType.BOOLEAN),
    field("tags", FieldType.ARRAY),
    field("meta", FieldType.JSON),
]


def sample_rows(count):
    return [
        {
            "id": i,
            "label": f"row-{i}",
            "amount": i * 1.5,
            "active": i % 2 == 0,
            "tags": ["a", "b"],
            "meta": {"k": "v"},
        }
        for i in range(count)
    ]


def write_all(path, job_format, rows, chunk=BUFFER_ROWS):
    writer = open_writer(job_format, path, FIELDS)
    for index, row in enumerate(rows, 1):
        writer.write(row)
        if index % chunk == 0:
            writer.checkpoint()
    writer.close()
    return path


def read_back(path, job_format):
    """Read with the format's own reader — the only honest verification."""
    if job_format == JobFormat.PARQUET:
        import pyarrow.parquet as pq

        return pq.read_table(path).to_pylist()
    if job_format == JobFormat.ORC:
        import pyarrow.orc as orc

        return orc.read_table(path).to_pylist()
    if job_format == JobFormat.AVRO:
        import fastavro

        with path.open("rb") as handle:
            return list(fastavro.reader(handle))
    if job_format == JobFormat.CSV:
        import csv

        with path.open() as handle:
            return list(csv.DictReader(handle))
    return [line for line in path.open() if line.strip()]


ALL_FORMATS = list(JobFormat)
BINARY_FORMATS = [JobFormat.PARQUET, JobFormat.ORC, JobFormat.AVRO]


def _skip_if_missing(job_format):
    if job_format in (JobFormat.PARQUET, JobFormat.ORC) and not install.is_available("parquet"):
        pytest.skip("optional 'parquet' extra is not installed")
    if job_format == JobFormat.AVRO and not install.is_available("avro"):
        pytest.skip("optional 'avro' extra is not installed")


@pytest.mark.parametrize("job_format", ALL_FORMATS)
def test_every_format_round_trips_every_row(job_format, tmp_path):
    _skip_if_missing(job_format)
    rows = sample_rows(1200)
    path = write_all(tmp_path / f"out.{suffix_for(job_format)}", job_format, rows)
    assert len(read_back(path, job_format)) == 1200


@pytest.mark.parametrize("job_format", ALL_FORMATS)
def test_a_zero_row_file_is_still_readable(job_format, tmp_path):
    """Regression: an ORC writer closed without a single batch produced a
    file too short to open ("File size too small") rather than an empty
    table. An empty result must be empty, not corrupt."""
    _skip_if_missing(job_format)
    path = tmp_path / f"empty.{suffix_for(job_format)}"
    open_writer(job_format, path, FIELDS).close()
    assert read_back(path, job_format) == []


@requires_parquet
def test_parquet_writes_one_row_group_per_chunk_rather_than_buffering(tmp_path):
    """The whole reason a columnar format is allowed here at all: Phase 8's
    rule is that a job format must stream, and row groups are what make
    that true. One group for the entire run would mean the dataset was
    held in memory."""
    import pyarrow.parquet as pq

    rows = sample_rows(BUFFER_ROWS * 3)
    path = write_all(tmp_path / "out.parquet", JobFormat.PARQUET, rows)
    assert pq.ParquetFile(path).num_row_groups >= 3


@pytest.mark.parametrize("job_format", BINARY_FORMATS)
def test_a_list_stays_a_list(job_format, tmp_path):
    """All three formats have list types and the generator always produces
    a list of strings, so flattening it to a JSON string would be losing
    structure the format can hold."""
    _skip_if_missing(job_format)
    path = write_all(tmp_path / f"out.{suffix_for(job_format)}", job_format, sample_rows(3))
    assert read_back(path, job_format)[0]["tags"] == ["a", "b"]


@pytest.mark.parametrize("job_format", BINARY_FORMATS)
def test_an_object_becomes_json_text(job_format, tmp_path):
    """Unlike a list, the generator's object keys are themselves random —
    there is no fixed struct to declare, so a JSON string is the honest
    representation rather than a lost one."""
    _skip_if_missing(job_format)
    path = write_all(tmp_path / f"out.{suffix_for(job_format)}", job_format, sample_rows(3))
    assert read_back(path, job_format)[0]["meta"] == '{"k": "v"}'


@pytest.mark.parametrize("job_format", BINARY_FORMATS)
def test_types_survive_the_round_trip(job_format, tmp_path):
    """CSV loses every type; these formats are chosen precisely because
    they don't."""
    _skip_if_missing(job_format)
    path = write_all(tmp_path / f"out.{suffix_for(job_format)}", job_format, sample_rows(5))
    first = read_back(path, job_format)[0]
    assert isinstance(first["id"], int)
    assert isinstance(first["amount"], float)
    assert isinstance(first["active"], bool)


@pytest.mark.parametrize("job_format", ALL_FORMATS)
def test_each_format_has_its_own_suffix(job_format):
    """The download filename is built from this; a Parquet file named .jsonl
    is a support ticket."""
    assert suffix_for(job_format) == job_format.value


def test_a_format_needing_a_missing_extra_says_which_one(monkeypatch):
    monkeypatch.setattr(install, "is_available", lambda key: False)
    with pytest.raises(ValueError) as exc:
        open_writer(JobFormat.PARQUET, "unused.parquet", FIELDS)
    assert "parquet" in str(exc.value)


def test_csv_and_jsonl_need_no_extra_at_all(tmp_path, monkeypatch):
    """They are stdlib, so a core install must keep working when every
    optional extra is absent."""
    monkeypatch.setattr(install, "is_available", lambda key: False)
    for job_format in (JobFormat.CSV, JobFormat.JSONL):
        path = write_all(tmp_path / f"core.{suffix_for(job_format)}", job_format, sample_rows(10))
        assert len(read_back(path, job_format)) == 10
