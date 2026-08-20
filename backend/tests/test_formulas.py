def _create_project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Retail"}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="LineItem"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_formula_field_computed_from_other_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "price",
            "field_type": "float",
            "order": 0,
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 100,
        },
        headers=auth_headers,
    )
    client.post(
        f"{base}/fields",
        json={
            "name": "quantity",
            "field_type": "integer",
            "order": 1,
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 10,
        },
        headers=auth_headers,
    )
    total_resp = client.post(
        f"{base}/fields",
        json={
            "name": "total",
            "field_type": "float",
            "order": 2,
            "required": True,
            "nullable": False,
            "formula": "price * quantity",
        },
        headers=auth_headers,
    )
    assert total_resp.status_code == 201

    resp = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert resp.status_code == 200
    for row in resp.json():
        assert row["total"] == row["price"] * row["quantity"]


def test_formula_referencing_unknown_field_rejected_at_creation(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "total",
            "field_type": "float",
            "formula": "price * quantity",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
