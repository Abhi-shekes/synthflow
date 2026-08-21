def _create_project(client, headers, name="Frontend Team"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(client, headers, project_id, name="Product"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "sku", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    )
    return entity["id"]


def test_create_rest_output_and_fetch_publicly(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs"

    created = client.post(base, json={"default_count": 7}, headers=auth_headers)
    assert created.status_code == 201
    token = created.json()["token"]
    assert token

    # No Authorization header at all — this is the point.
    resp = client.get(f"/public/rest/{token}")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 7
    assert all("sku" in row for row in rows)


def test_public_endpoint_respects_count_override(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs"
    created = client.post(base, json={"default_count": 5}, headers=auth_headers).json()

    resp = client.get(f"/public/rest/{created['token']}?count=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_public_endpoint_returns_different_rows_each_call(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs"
    created = client.post(base, json={"default_count": 20}, headers=auth_headers).json()

    first = client.get(f"/public/rest/{created['token']}").json()
    second = client.get(f"/public/rest/{created['token']}").json()
    assert first != second


def test_unknown_token_returns_404(client):
    resp = client.get("/public/rest/does-not-exist")
    assert resp.status_code == 404


def test_delete_rest_output_revokes_token(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs"
    created = client.post(base, json={"default_count": 5}, headers=auth_headers).json()

    deleted = client.delete(f"{base}/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    resp = client.get(f"/public/rest/{created['token']}")
    assert resp.status_code == 404


def test_rest_output_requires_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/rest-outputs",
        json={"default_count": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_outputs_aggregate_endpoint(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs",
        json={"default_count": 5},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json={
            "name": "Warehouse",
            "dialect": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "warehouse",
            "username": "synthflow",
            "password": "secret",
        },
        headers=auth_headers,
    )

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    types = {o["type"] for o in resp.json()}
    assert types == {"rest", "database"}
