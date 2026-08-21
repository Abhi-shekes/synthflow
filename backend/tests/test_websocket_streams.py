def _create_project(client, headers, name="Sensors"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(client, headers, project_id, name="Reading"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "temperature", "field_type": "integer", "required": True, "nullable": False},
        headers=headers,
    )
    return entity["id"]


def test_create_stream_and_receive_messages(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams"

    created = client.post(
        base, json={"events_per_second": 20, "batch_size": 3}, headers=auth_headers
    )
    assert created.status_code == 201
    token = created.json()["token"]

    with client.websocket_connect(f"/public/stream/{token}") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert len(first) == 3
    assert all("temperature" in row for row in first)
    assert len(second) == 3
    # Independently generated batches shouldn't be identical.
    assert first != second


def test_stream_rejects_unknown_token(client):
    with client.websocket_connect("/public/stream/does-not-exist") as ws:
        message = ws.receive_json()
        assert "error" in message


def test_list_and_delete_stream(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams"

    created = client.post(base, json={"events_per_second": 5}, headers=auth_headers).json()

    listed = client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(f"{base}/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get(base, headers=auth_headers)
    assert listed_after.json() == []


def test_deleting_stream_stops_an_open_connection(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams"

    created = client.post(base, json={"events_per_second": 30}, headers=auth_headers).json()

    with client.websocket_connect(f"/public/stream/{created['token']}") as ws:
        ws.receive_json()  # first batch succeeds
        client.delete(f"{base}/{created['id']}", headers=auth_headers)
        message = ws.receive_json()  # next tick re-checks the token and finds it gone
        assert "error" in message


def test_stream_requires_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/websocket-streams",
        json={"events_per_second": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_events_per_second_out_of_range_rejected(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams"

    resp = client.post(base, json={"events_per_second": 0}, headers=auth_headers)
    assert resp.status_code == 422

    resp = client.post(base, json={"events_per_second": 1000}, headers=auth_headers)
    assert resp.status_code == 422


def test_stream_appears_in_outputs_aggregate(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams"
    client.post(base, json={"events_per_second": 5}, headers=auth_headers)

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    assert any(o["type"] == "websocket" for o in resp.json())
