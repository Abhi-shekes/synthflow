import io

from openpyxl import Workbook

from app.core.config import settings


def _create_project(client, headers, name="Reference Data"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(
    client, headers, project_id, field_payload, entity_name="Record"
):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": entity_name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json=field_payload,
        headers=headers,
    ).json()
    return entity["id"], field["id"]


def _upload(client, headers, project_id, name, filename, content, content_type):
    return client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": name},
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_upload_csv_creates_lookup_table_with_coerced_types(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    csv_content = b"name,population\nSpringfield,1000\nShelbyville,2000\n"

    resp = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", csv_content, "text/csv"
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Cities"
    assert body["columns"] == ["name", "population"]
    assert body["row_count"] == 2
    assert body["preview"] == [
        {"name": "Springfield", "population": 1000},
        {"name": "Shelbyville", "population": 2000},
    ]


def test_upload_json_preserves_native_types(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    json_content = b'[{"code": "US", "digits": 1}, {"code": "IN", "digits": 91}]'

    resp = _upload(
        client,
        auth_headers,
        project_id,
        "Dialing codes",
        "codes.json",
        json_content,
        "application/json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["columns"] == ["code", "digits"]
    assert body["row_count"] == 2
    assert body["preview"][0] == {"code": "US", "digits": 1}


def test_upload_excel_creates_lookup_table(client, auth_headers):
    project_id = _create_project(client, auth_headers)

    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "price"])
    ws.append(["A1", 9.99])
    ws.append(["A2", 19.99])
    buffer = io.BytesIO()
    wb.save(buffer)

    resp = _upload(
        client,
        auth_headers,
        project_id,
        "Prices",
        "prices.xlsx",
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["columns"] == ["sku", "price"]
    assert body["row_count"] == 2
    assert body["preview"][0] == {"sku": "A1", "price": 9.99}


def test_reject_unsupported_file_type(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = _upload(
        client, auth_headers, project_id, "Notes", "notes.txt", b"hello", "text/plain"
    )
    assert resp.status_code == 400


def test_reject_empty_csv(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = _upload(
        client, auth_headers, project_id, "Empty", "empty.csv", b"name\n", "text/csv"
    )
    assert resp.status_code == 400


def test_reject_file_exceeding_row_limit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAX_LOOKUP_ROWS", 2)
    project_id = _create_project(client, auth_headers)
    csv_content = b"n\n1\n2\n3\n"
    resp = _upload(
        client, auth_headers, project_id, "TooBig", "big.csv", csv_content, "text/csv"
    )
    assert resp.status_code == 400


def test_delete_lookup_table(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    created = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()

    deleted = client.delete(
        f"/api/v1/projects/{project_id}/lookup-tables/{created['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204

    listed = client.get(
        f"/api/v1/projects/{project_id}/lookup-tables", headers=auth_headers
    )
    assert listed.json() == []


def test_lookup_attachment_field_must_belong_to_entity(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, _field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    other_entity_id, other_field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "other", "field_type": "string", "required": True, "nullable": False},
        entity_name="Other",
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments",
        json={
            "field_id": other_field_id,
            "lookup_table_id": lookup_table["id"],
            "column": "name",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_lookup_attachment_table_must_belong_to_project(client, auth_headers):
    project_a = _create_project(client, auth_headers, "A")
    project_b = _create_project(client, auth_headers, "B")
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_b,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client, auth_headers, project_a, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_b}/entities/{entity_id}/lookup-attachments",
        json={"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "name"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_lookup_attachment_column_must_exist(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments",
        json={
            "field_id": field_id,
            "lookup_table_id": lookup_table["id"],
            "column": "nonexistent",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_only_one_lookup_attachment_per_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()

    payload = {"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "name"}
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments"
    first = client.post(base, json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = client.post(base, json=payload, headers=auth_headers)
    assert second.status_code == 400


def test_delete_lookup_attachment(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments"
    attachment = client.post(
        base,
        json={"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "name"},
        headers=auth_headers,
    ).json()

    deleted = client.delete(f"{base}/{attachment['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(base, headers=auth_headers)
    assert listed.json() == []


def test_deleting_lookup_table_cascades_to_attachment(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Cities", "cities.csv", b"name\nA\nB\n", "text/csv"
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments",
        json={"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "name"},
        headers=auth_headers,
    )

    client.delete(
        f"/api/v1/projects/{project_id}/lookup-tables/{lookup_table['id']}",
        headers=auth_headers,
    )

    entity = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}", headers=auth_headers
    ).json()
    assert entity["lookup_attachments"] == []


def test_single_entity_generate_draws_from_lookup_table(client, auth_headers):
    """Unlike a Relationship, a lookup doesn't need project-wide generation —
    it works from the single-entity /generate endpoint directly."""
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "company", "field_type": "string", "required": True, "nullable": False},
    )
    lookup_table = _upload(
        client,
        auth_headers,
        project_id,
        "Companies",
        "companies.csv",
        b"name\nACME\n",
        "text/csv",
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments",
        json={"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "name"},
        headers=auth_headers,
    )

    gen = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 5},
        headers=auth_headers,
    )
    assert gen.status_code == 200
    rows = gen.json()
    assert len(rows) == 5
    assert all(row["company"] == "ACME" for row in rows)


def test_unique_field_exhausts_small_lookup_pool(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {
            "name": "code",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "unique": True,
        },
    )
    lookup_table = _upload(
        client, auth_headers, project_id, "Codes", "codes.csv", b"code\nA\nB\n", "text/csv"
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/lookup-attachments",
        json={"field_id": field_id, "lookup_table_id": lookup_table["id"], "column": "code"},
        headers=auth_headers,
    )

    gen = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 3},
        headers=auth_headers,
    )
    assert gen.status_code == 400
