def _create_project(client, headers, name="Analytics"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


CONNECTION_PAYLOAD = {
    "name": "Warehouse",
    "dialect": "postgresql",
    "host": "localhost",
    "port": 5432,
    "database": "warehouse",
    "username": "synthflow",
    "password": "super-secret",
}


def test_create_connection_never_returns_password(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json=CONNECTION_PAYLOAD,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "password" not in body
    assert body["host"] == "localhost"


def test_list_connections_never_returns_password(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json=CONNECTION_PAYLOAD,
        headers=auth_headers,
    )
    resp = client.get(f"/api/v1/projects/{project_id}/database-connections", headers=auth_headers)
    assert resp.status_code == 200
    assert all("password" not in c for c in resp.json())


def test_delete_connection(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    connection = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json=CONNECTION_PAYLOAD,
        headers=auth_headers,
    ).json()

    deleted = client.delete(
        f"/api/v1/projects/{project_id}/database-connections/{connection['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    listed = client.get(f"/api/v1/projects/{project_id}/database-connections", headers=auth_headers)
    assert listed.json() == []


def test_connections_are_scoped_per_project(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    other_project_id = _create_project(client, auth_headers, "Other")
    connection = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json=CONNECTION_PAYLOAD,
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/projects/{other_project_id}/database-connections/{connection['id']}/test",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_test_connection_reports_failure_for_unreachable_host(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    connection = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json={**CONNECTION_PAYLOAD, "host": "does-not-resolve.invalid", "port": 5432},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/database-connections/{connection['id']}/test",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["detail"]


def test_mysql_and_mongodb_connections_can_be_created(client, auth_headers):
    """Both were modelled long before they worked; Phase 12 makes them real,
    and the API shape is unchanged for either."""
    project_id = _create_project(client, auth_headers)
    for dialect, port in (("mysql", 3306), ("mongodb", 27017)):
        response = client.post(
            f"/api/v1/projects/{project_id}/database-connections",
            json={**CONNECTION_PAYLOAD, "dialect": dialect, "port": port},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["dialect"] == dialect
        assert "password" not in response.json()


def test_push_rejects_unsafe_table_name(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    connection = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json=CONNECTION_PAYLOAD,
        headers=auth_headers,
    ).json()
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Row"}, headers=auth_headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/database-connections/{connection['id']}/push",
        json={"entity_id": entity["id"], "count": 5, "table_name": "users; DROP TABLE users;"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "safe SQL identifier" in resp.json()["detail"]
