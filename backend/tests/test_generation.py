def _create_project(client, headers):
    resp = client.post("/api/v1/projects", json={"name": "Retail"}, headers=headers)
    return resp.json()["id"]


def _create_entity(client, headers, project_id):
    resp = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Customer"}, headers=headers
    )
    return resp.json()["id"]


def test_generate_rows_respects_field_definitions(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "customer_id",
            "field_type": "uuid",
            "required": True,
            "nullable": False,
            "unique": True,
        },
        headers=auth_headers,
    )
    client.post(
        f"{base}/fields",
        json={
            "name": "age",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": 18,
            "max_value": 25,
        },
        headers=auth_headers,
    )
    client.post(
        f"{base}/fields",
        json={
            "name": "tier",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["bronze", "silver", "gold"],
        },
        headers=auth_headers,
    )

    resp = client.post(f"{base}/generate", json={"count": 25}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 25

    ids = [row["customer_id"] for row in rows]
    assert len(ids) == len(set(ids))  # unique constraint held

    for row in rows:
        assert 18 <= row["age"] <= 25
        assert row["tier"] in {"bronze", "silver", "gold"}


def test_generate_requires_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 400


def test_generate_count_bounds(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    client.post(
        f"{base}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    )

    resp = client.post(f"{base}/generate", json={"count": 0}, headers=auth_headers)
    assert resp.status_code == 400

    resp = client.post(f"{base}/generate", json={"count": 999999}, headers=auth_headers)
    assert resp.status_code == 400
