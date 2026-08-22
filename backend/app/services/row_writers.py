"""How a job's rows become a file.

Phase 8 shipped CSV and JSONL with the writing logic inline in
`jobs._write_entity`, which was right for two formats and would have become
an if-chain at five. This is that logic behind one small interface, so a new
format is a class rather than another branch in the middle of the progress
and cancellation loop.

**Every format here streams.** That was Phase 8's stated reason for
offering only CSV and JSONL — a job exists precisely for output too large
to hold in memory, so a format needing the whole result before the first
byte would defeat it. Parquet and ORC look like exceptions and aren't:
both are built from row *groups*, and this writes one per chunk instead of
buffering the run. The peak memory is a chunk, not a dataset. Avro is
block-structured and behaves the same way.

`checkpoint()` is called by the job loop on the same boundary where it
publishes progress and honours a cancel request. That alignment is
deliberate: a cancel can only land where the file is in a valid state, so a
cancelled job leaves a readable partial file rather than a corrupt one.

pyarrow (Parquet, ORC) is 157 MB installed, which is exactly why it is an
optional extra and never core — see app.services.install.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Protocol

from app.models.field import EntityField, FieldType
from app.models.job import JobFormat
from app.services import install

# Rows buffered before a row group / block is written. Matched to the job
# loop's chunk so a checkpoint writes exactly what has accumulated.
BUFFER_ROWS = 500


class RowWriter(Protocol):
    """Write rows one at a time; flush on a boundary; finish cleanly."""

    def write(self, row: dict[str, Any]) -> None: ...

    def checkpoint(self) -> None: ...

    def close(self) -> None: ...


SUFFIXES: dict[JobFormat, str] = {
    JobFormat.CSV: "csv",
    JobFormat.JSONL: "jsonl",
    JobFormat.PARQUET: "parquet",
    JobFormat.ORC: "orc",
    JobFormat.AVRO: "avro",
}

# Which optional extra each format needs. CSV and JSONL are stdlib.
REQUIRED_EXTRA: dict[JobFormat, str | None] = {
    JobFormat.CSV: None,
    JobFormat.JSONL: None,
    JobFormat.PARQUET: "parquet",
    JobFormat.ORC: "parquet",
    JobFormat.AVRO: "avro",
}


def suffix_for(job_format: JobFormat) -> str:
    return SUFFIXES[job_format]


def _plain(value: Any) -> Any:
    """Flatten what a typed columnar schema can't hold.

    ARRAY stays a real list — Parquet, ORC and Avro all have list types and
    the generator always produces a list of strings, so the schema is
    knowable. OBJECT/JSON become a JSON string instead, because the
    generator's object keys are themselves random: there is no fixed struct
    to declare, and inventing one per row is not a schema.
    """
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    if isinstance(value, list):
        return [str(v) for v in value]
    return value


class _TextWriter:
    """CSV and JSONL — unchanged behaviour from Phase 8, moved here."""

    def __init__(self, path: Path, fields: list[EntityField], job_format: JobFormat) -> None:
        self._format = job_format
        self._names = [f.name for f in fields]
        self._handle = path.open("w", newline="", encoding="utf-8")
        self._csv = None
        if job_format == JobFormat.CSV:
            self._csv = csv.DictWriter(self._handle, fieldnames=self._names, extrasaction="ignore")
            self._csv.writeheader()

    def write(self, row: dict[str, Any]) -> None:
        if self._csv is not None:
            self._csv.writerow(row)
        else:
            self._handle.write(json.dumps(row, default=str) + "\n")

    def checkpoint(self) -> None:
        # Flush so a reader (or a crash) sees real rows.
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def _arrow_type(field: EntityField):
    import pyarrow as pa

    # DATE and DATETIME are deliberately strings. The generator emits ISO
    # text, and parsing it into a timestamp here would make the file's
    # contents depend on this module's timezone assumptions rather than on
    # what was generated. A consumer that wants timestamps can cast, which
    # is an explicit choice they make with their own timezone in hand.
    mapping = {
        FieldType.STRING: pa.string(),
        FieldType.INTEGER: pa.int64(),
        FieldType.FLOAT: pa.float64(),
        FieldType.BOOLEAN: pa.bool_(),
        FieldType.DATE: pa.string(),
        FieldType.DATETIME: pa.string(),
        FieldType.UUID: pa.string(),
        FieldType.ENUM: pa.string(),
        FieldType.ARRAY: pa.list_(pa.string()),
        FieldType.OBJECT: pa.string(),
        FieldType.JSON: pa.string(),
    }
    return mapping.get(field.field_type, pa.string())


class _ArrowWriter:
    """Parquet and ORC, via pyarrow. One row group per checkpoint."""

    def __init__(self, path: Path, fields: list[EntityField], job_format: JobFormat) -> None:
        import pyarrow as pa

        self._pa = pa
        self._names = [f.name for f in fields]
        self._schema = pa.schema([pa.field(f.name, _arrow_type(f)) for f in fields])
        self._buffer: list[dict[str, Any]] = []
        self._wrote_any = False

        # The two writers spell "append this batch" differently —
        # ParquetWriter.write_table vs ORCWriter.write — so the method is
        # bound once here rather than branched on in the hot loop.
        if job_format == JobFormat.PARQUET:
            import pyarrow.parquet as pq

            self._writer = pq.ParquetWriter(str(path), self._schema)
            self._append = self._writer.write_table
        else:
            import pyarrow.orc as orc

            self._writer = orc.ORCWriter(str(path))
            self._append = self._writer.write

    def write(self, row: dict[str, Any]) -> None:
        self._buffer.append({name: _plain(row.get(name)) for name in self._names})
        if len(self._buffer) >= BUFFER_ROWS:
            self._drain()

    def _drain(self) -> None:
        if not self._buffer:
            return
        table = self._pa.Table.from_pylist(self._buffer, schema=self._schema)
        self._append(table)
        self._wrote_any = True
        self._buffer.clear()

    def checkpoint(self) -> None:
        self._drain()

    def close(self) -> None:
        try:
            self._drain()
            if not self._wrote_any:
                # An ORC writer closed without a single batch emits a file
                # too short to open — "File size too small" rather than an
                # empty table. Writing one empty batch gives it the schema
                # it needs. Parquet is unaffected but takes the same path,
                # since two behaviours here would be a trap for whichever
                # one someone tested with.
                self._append(self._pa.Table.from_pylist([], schema=self._schema))
        finally:
            self._writer.close()


def _avro_type(field: EntityField):
    mapping = {
        FieldType.STRING: "string",
        FieldType.INTEGER: "long",
        FieldType.FLOAT: "double",
        FieldType.BOOLEAN: "boolean",
        FieldType.DATE: "string",
        FieldType.DATETIME: "string",
        FieldType.UUID: "string",
        FieldType.ENUM: "string",
        FieldType.ARRAY: {"type": "array", "items": "string"},
        FieldType.OBJECT: "string",
        FieldType.JSON: "string",
    }
    inner = mapping.get(field.field_type, "string")
    # Every field is nullable in the schema regardless of its `required`
    # flag: error injection can null any value at generation time, and a
    # schema that refuses that would make the file unwritable for exactly
    # the runs it is most useful to inspect.
    return ["null", inner]


class _AvroWriter:
    """Avro, via fastavro's incremental `Writer`.

    `Writer` handles block boundaries itself and exposes `write(record)` and
    `flush()`, so this is the one format that needs no buffering of its own.
    The module-level `writer()` helper would have needed the file reopened
    in append mode for every block after the first, which is a worse fit for
    a long-running job holding one handle.
    """

    def __init__(self, path: Path, fields: list[EntityField], job_format: JobFormat) -> None:
        from fastavro.write import Writer

        self._names = [f.name for f in fields]
        self._handle = path.open("wb")
        self._writer = Writer(
            self._handle,
            {
                "type": "record",
                "name": "Row",
                "fields": [{"name": f.name, "type": _avro_type(f)} for f in fields],
            },
        )

    def write(self, row: dict[str, Any]) -> None:
        self._writer.write({name: _plain(row.get(name)) for name in self._names})

    def checkpoint(self) -> None:
        self._writer.flush()
        self._handle.flush()

    def close(self) -> None:
        try:
            # Flushes the final block and the header, so a zero-row job
            # still produces a readable file rather than an empty one.
            self._writer.flush()
        finally:
            self._handle.close()


def open_writer(job_format: JobFormat, path: Path, fields: list[EntityField]) -> RowWriter:
    """A writer for `job_format`, or a clear error naming the missing extra."""
    extra = REQUIRED_EXTRA[job_format]
    if extra is not None:
        install.require(extra)

    if job_format in (JobFormat.CSV, JobFormat.JSONL):
        return _TextWriter(path, fields, job_format)
    if job_format in (JobFormat.PARQUET, JobFormat.ORC):
        return _ArrowWriter(path, fields, job_format)
    return _AvroWriter(path, fields, job_format)
