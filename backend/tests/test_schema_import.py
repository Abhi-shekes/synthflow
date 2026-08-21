"""Phase 7 schema import.

The assertion that matters most in here isn't that the shapes look right —
it's that an imported template survives `POST /projects/import` and then
actually generates rows. An importer that produces a plausible-looking
template the rest of the system rejects would be worse than useless, and
only a round-trip catches that.
"""

import io
import json

import pytest

from app.services.schema_import import (
    JSONSchemaImportError,
    SampleImportError,
    SQLImportError,
    import_from_json_schema,
    import_from_sample,
    import_from_sql,
)
from app.services.schema_import.common import (
    dedupe,
    sanitize_identifier,
    sql_type_to_field_type,
)

SIMPLE_DDL = """
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    credit_score SMALLINT,
    signed_up TIMESTAMP NOT NULL
);
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    total NUMERIC(10,2) NOT NULL
);
"""


def _import_and_generate(client, headers, template: dict, count: int = 5) -> dict:
    """Apply a template through the real import route, then generate."""
    created = client.post("/api/v1/projects/import", json=template, headers=headers)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    generated = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"count": count, "counts": {}},
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    return generated.json()


# ------------------------------------------------------------- helpers


def test_sanitize_identifier_produces_usable_names():
    assert sanitize_identifier("full name") == "full_name"
    assert sanitize_identifier("order-total") == "order_total"
    assert sanitize_identifier("2fa", fallback="col") == "col_2fa"
    # Python keywords would break expression parsing.
    assert sanitize_identifier("class") == "class_"
    assert sanitize_identifier("!!!", fallback="col") == "col"


def test_dedupe_resolves_collisions():
    taken: set[str] = set()
    assert dedupe("name", taken) == "name"
    assert dedupe("name", taken) == "name_2"
    assert dedupe("name", taken) == "name_3"


@pytest.mark.parametrize(
    ("sql_type", "expected", "exact"),
    [
        ("timestamp without time zone", "datetime", True),
        ("TIMESTAMP", "datetime", True),
        ("DATE", "date", True),
        ("BIGINT", "integer", True),
        ("NUMERIC(10,2)", "float", True),
        ("BOOLEAN", "boolean", True),
        ("UUID", "uuid", True),
        ("JSONB", "json", True),
        ("VARCHAR(50)", "string", True),
        # No SynthFlow equivalent — must be reported, not silently mapped.
        ("TIME", "string", False),
        ("TSVECTOR", "string", False),
    ],
)
def test_sql_type_mapping(sql_type, expected, exact):
    mapped, was_exact = sql_type_to_field_type(sql_type)
    assert mapped == expected
    assert was_exact is exact


# ----------------------------------------------------------- SQL / DDL


def test_sql_import_maps_columns_constraints_and_keys():
    result = import_from_sql(SIMPLE_DDL, dialect="postgres")
    entities = {e.name: e for e in result.template.entities}
    assert set(entities) == {"customers", "orders"}

    fields = {f.name: f for f in entities["customers"].fields}
    assert fields["id"].field_type == "integer"
    assert fields["id"].unique is True
    assert fields["email"].required is True
    assert fields["email"].unique is True
    assert fields["credit_score"].required is False
    assert fields["signed_up"].field_type == "datetime"
    assert fields["signed_up"].required is True


def test_sql_import_reads_both_inline_and_table_level_foreign_keys():
    ddl = (
        SIMPLE_DDL
        + """
    CREATE TABLE line_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );
    """
    )
    result = import_from_sql(ddl, dialect="postgres")
    links = {
        (r.source_entity, r.source_field, r.target_entity, r.target_field)
        for r in result.template.relationships
    }
    # Inline REFERENCES on the column...
    assert ("orders", "customer_id", "customers", "id") in links
    # ...and a table-level FOREIGN KEY clause.
    assert ("line_items", "order_id", "orders", "id") in links


def test_sql_import_respects_explicit_null():
    result = import_from_sql(
        "CREATE TABLE t (a INTEGER NOT NULL, b INTEGER NULL, c INTEGER);",
        dialect="postgres",
    )
    fields = {f.name: f for f in result.template.entities[0].fields}
    assert fields["a"].required is True
    assert fields["b"].required is False
    assert fields["c"].required is False


def test_sql_import_caps_integer_range_to_the_column_width():
    result = import_from_sql("CREATE TABLE t (small SMALLINT);", dialect="postgres")
    field = result.template.entities[0].fields[0]
    # A smallint must not generate values it couldn't store.
    assert field.max_value is not None and field.max_value <= 32767


def test_sql_import_turns_serial_keys_into_auto_increment_trends():
    """A SERIAL primary key should generate 1, 2, 3… not random large
    integers — SynthFlow expresses that as a linear trend (see the Phase 2
    note on auto-increment) rather than a dedicated flag."""
    result = import_from_sql(SIMPLE_DDL, dialect="postgres")
    trends = {(t.entity, t.field): t for t in result.template.trends}

    assert ("customers", "id") in trends
    assert ("orders", "id") in trends
    trend = trends[("customers", "id")]
    assert trend.trend_type == "linear"
    assert trend.params == {"start": 1, "slope": 1}
    # A plain INTEGER column must not get one.
    assert ("orders", "customer_id") not in trends


def test_imported_auto_increment_actually_generates_sequential_ids(client, auth_headers):
    result = import_from_sql(SIMPLE_DDL, dialect="postgres")
    body = _import_and_generate(client, auth_headers, result.template.model_dump(), count=6)

    ids = [row["id"] for row in body["customers"]]
    assert ids == [1, 2, 3, 4, 5, 6]


def test_sql_import_reports_what_it_could_not_represent():
    ddl = """
    CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        "odd name" TEXT,
        pickup TIME,
        CHECK (id > 0)
    );
    CREATE INDEX idx_t ON t(id);
    """
    result = import_from_sql(ddl, dialect="postgres")
    joined = " | ".join(result.warnings)
    assert "CHECK" in joined
    assert "odd name" in joined
    assert "TIME" in joined
    assert "CREATE INDEX" in joined


def test_sql_import_rejects_input_with_no_tables():
    with pytest.raises(SQLImportError):
        import_from_sql("SELECT 1;")
    with pytest.raises(SQLImportError):
        import_from_sql("   ")


def test_sql_import_round_trips_into_a_working_project(client, auth_headers):
    result = import_from_sql(SIMPLE_DDL, dialect="postgres")
    body = _import_and_generate(client, auth_headers, result.template.model_dump())

    assert set(body) == {"customers", "orders"}
    assert len(body["orders"]) == 5
    customer_ids = {row["id"] for row in body["customers"]}
    # The imported foreign key must produce genuinely referential data.
    for order in body["orders"]:
        assert order["customer_id"] in customer_ids


# --------------------------------------------------------- JSON Schema


def test_json_schema_import_maps_types_formats_and_enums():
    document = {
        "title": "Person",
        "type": "object",
        "required": ["id", "email"],
        "properties": {
            "id": {"type": "integer", "minimum": 1, "maximum": 999},
            "email": {"type": "string", "format": "email"},
            "born": {"type": "string", "format": "date"},
            "ref": {"type": "string", "format": "uuid"},
            "status": {"type": "string", "enum": ["active", "banned"]},
            "score": {"type": "number"},
            "tags": {"type": "array"},
            "maybe": {"type": ["string", "null"]},
        },
    }
    result = import_from_json_schema(document)
    fields = {f.name: f for f in result.template.entities[0].fields}

    assert fields["id"].field_type == "integer"
    assert fields["id"].required is True
    assert (fields["id"].min_value, fields["id"].max_value) == (1.0, 999.0)
    assert fields["born"].field_type == "date"
    assert fields["ref"].field_type == "uuid"
    assert fields["status"].field_type == "enum"
    assert fields["status"].enum_values == ["active", "banned"]
    assert fields["score"].field_type == "float"
    assert fields["tags"].field_type == "array"
    assert fields["maybe"].field_type == "string"
    assert fields["email"].required is True


def test_json_schema_nested_object_becomes_its_own_linked_entity():
    document = {
        "title": "Order",
        "type": "object",
        "properties": {
            "total": {"type": "number"},
            "address": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        },
    }
    result = import_from_json_schema(document)
    names = {e.name for e in result.template.entities}
    assert "Order" in names
    assert "Order_address" in names

    assert len(result.template.relationships) == 1
    link = result.template.relationships[0]
    assert link.source_entity == "Order_address"
    assert link.target_entity == "Order"
    assert any("flat rows" in w for w in result.warnings)


def test_json_schema_resolves_local_refs_and_reports_remote_ones():
    document = {
        "title": "Root",
        "type": "object",
        "properties": {
            "local": {"$ref": "#/$defs/Thing"},
            "remote": {"$ref": "https://example.com/schema.json"},
        },
        "$defs": {"Thing": {"type": "integer"}},
    }
    result = import_from_json_schema(document)
    fields = {f.name: f for f in result.template.entities[0].fields}
    assert fields["local"].field_type == "integer"
    assert "remote" not in fields
    assert any("never make network calls" in w for w in result.warnings)


def test_openapi_document_imports_its_component_schemas():
    document = {
        "openapi": "3.0.0",
        "info": {"title": "Shop API"},
        "paths": {},
        "components": {
            "schemas": {
                "Product": {
                    "type": "object",
                    "required": ["sku"],
                    "properties": {
                        "sku": {"type": "string"},
                        "price": {"type": "number"},
                    },
                }
            }
        },
    }
    result = import_from_json_schema(document)
    assert result.template.name == "Shop API"
    assert [e.name for e in result.template.entities] == ["Product"]


def test_openapi_without_component_schemas_is_rejected_clearly():
    with pytest.raises(JSONSchemaImportError) as excinfo:
        import_from_json_schema({"openapi": "3.0.0", "info": {"title": "x"}, "paths": {}})
    assert "components.schemas" in str(excinfo.value)


def test_json_schema_import_round_trips_into_a_working_project(client, auth_headers):
    document = {
        "title": "Person",
        "type": "object",
        "required": ["id"],
        "properties": {
            "id": {"type": "integer", "minimum": 1, "maximum": 100},
            "status": {"type": "string", "enum": ["active", "banned"]},
        },
    }
    result = import_from_json_schema(document)
    body = _import_and_generate(client, auth_headers, result.template.model_dump())

    for row in body["Person"]:
        assert 1 <= row["id"] <= 100
        assert row["status"] in ("active", "banned")


# --------------------------------------------------------- sample data


SAMPLE_CSV = (
    b"id,email,age,status,joined,ratio,note\n"
    b"1,a@x.com,34,active,2024-01-05,1.5,hello\n"
    b"2,b@x.com,28,active,2024-02-06,2.5,\n"
    b"3,c@x.com,41,banned,2024-03-07,3.5,world\n"
    b"4,d@x.com,55,active,2024-04-08,4.5,again\n"
    b"5,e@x.com,23,banned,2024-05-09,5.5,more\n"
)


def test_sample_import_infers_types_ranges_and_enums():
    result = import_from_sample("people.csv", SAMPLE_CSV, max_rows=1000)
    fields = {f.name: f for f in result.template.entities[0].fields}

    assert fields["id"].field_type == "integer"
    assert fields["id"].unique is True
    assert fields["age"].field_type == "integer"
    assert (fields["age"].min_value, fields["age"].max_value) == (23.0, 55.0)
    assert fields["ratio"].field_type == "float"
    assert fields["joined"].field_type == "date"
    # Low cardinality over enough rows -> enum, not free text.
    assert fields["status"].field_type == "enum"
    assert fields["status"].enum_values == ["active", "banned"]
    # One blank cell means the column is nullable.
    assert fields["note"].required is False


def test_sample_import_is_honest_that_it_is_not_distribution_fitting():
    result = import_from_sample("people.csv", SAMPLE_CSV, max_rows=1000)
    assert any("not the real distribution" in w for w in result.warnings)


def test_sample_import_renames_columns_that_are_not_identifiers():
    csv = b"full name,order-total\nAda,10\nGrace,20\n"
    result = import_from_sample("s.csv", csv, max_rows=100)
    names = {f.name for f in result.template.entities[0].fields}
    assert names == {"full_name", "order_total"}
    assert any("renamed" in w for w in result.warnings)


def test_sample_import_handles_json_files():
    payload = json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]).encode()
    result = import_from_sample("s.json", payload, max_rows=100)
    fields = {f.name: f for f in result.template.entities[0].fields}
    assert fields["a"].field_type == "integer"


def test_sample_import_rejects_an_unsupported_file():
    with pytest.raises(SampleImportError):
        import_from_sample("s.txt", b"nope", max_rows=10)


def test_sample_import_round_trips_into_a_working_project(client, auth_headers):
    result = import_from_sample("people.csv", SAMPLE_CSV, max_rows=1000)
    body = _import_and_generate(client, auth_headers, result.template.model_dump())

    for row in body["people"]:
        assert 23 <= row["age"] <= 55
        assert row["status"] in ("active", "banned")


# ---------------------------------------------------------------- API


def test_sql_route_returns_a_template_and_warnings(client, auth_headers):
    resp = client.post(
        "/api/v1/schema-import/sql",
        json={"sql": SIMPLE_DDL, "dialect": "postgres"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {e["name"] for e in body["template"]["entities"]} == {"customers", "orders"}
    assert isinstance(body["warnings"], list)


def test_sql_route_rejects_unparseable_input(client, auth_headers):
    resp = client.post("/api/v1/schema-import/sql", json={"sql": "SELECT 1;"}, headers=auth_headers)
    assert resp.status_code == 400


def test_json_schema_route(client, auth_headers):
    resp = client.post(
        "/api/v1/schema-import/json-schema",
        json={
            "document": {
                "title": "T",
                "type": "object",
                "properties": {"a": {"type": "integer"}},
            }
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["template"]["entities"][0]["name"] == "T"


def test_sample_route_accepts_an_upload(client, auth_headers):
    resp = client.post(
        "/api/v1/schema-import/sample",
        files={"file": ("people.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["template"]["entities"][0]["name"] == "people"


def test_openapi_file_route_rejects_invalid_json(client, auth_headers):
    resp = client.post(
        "/api/v1/schema-import/openapi-file",
        files={"file": ("api.json", io.BytesIO(b"{not json"), "application/json")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_database_route_404s_for_an_unknown_connection(client, auth_headers):
    resp = client.post(
        "/api/v1/schema-import/database",
        json={"connection_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_import_routes_require_auth(client):
    assert client.post("/api/v1/schema-import/sql", json={"sql": "x"}).status_code == 401
    assert (
        client.post("/api/v1/schema-import/json-schema", json={"document": {}}).status_code == 401
    )


def test_importing_creates_nothing_until_the_template_is_applied(client, auth_headers):
    """The review step is structural: an import call must not create a
    project on its own."""
    before = len(client.get("/api/v1/projects", headers=auth_headers).json())

    resp = client.post(
        "/api/v1/schema-import/sql",
        json={"sql": SIMPLE_DDL, "dialect": "postgres"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    after = len(client.get("/api/v1/projects", headers=auth_headers).json())
    assert after == before
