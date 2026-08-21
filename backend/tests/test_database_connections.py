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


def test_mysql_dialect_accepted_but_not_yet_pushable(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    connection = client.post(
        f"/api/v1/projects/{project_id}/database-connections",
        json={**CONNECTION_PAYLOAD, "dialect": "mysql", "port": 3306},
        headers=auth_headers,
    )
    assert connection.status_code == 201

    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Row"}, headers=auth_headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/database-connections/{connection.json()['id']}/push",
        json={"entity_id": entity["id"], "count": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "not yet supported" in resp.json()["detail"]


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
