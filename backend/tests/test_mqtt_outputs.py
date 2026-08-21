"""CRUD-level coverage only — see test_kafka_outputs.py's module docstring
for why (no real broker in the test environment; live delivery is proven
via docker-compose instead) and why every successful create is followed
by a delete in the same test.
"""

import pytest

from app.services import install

requires_mqtt = pytest.mark.skipif(
    not install.is_available("mqtt"),
    reason="optional 'mqtt' extra is not installed in this environment",
)


def _create_project(client, headers, name="Streaming"):
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


@requires_mqtt
def test_create_list_and_delete_mqtt_output(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/mqtt-outputs"

    created = client.post(
        base,
        json={"broker_host": "localhost", "broker_port": 1883, "topic": "readings"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["broker_host"] == "localhost"
    assert body["broker_port"] == 1883
    assert body["topic"] == "readings"

    listed = client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(f"{base}/{body['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get(base, headers=auth_headers)
    assert listed_after.json() == []


def test_mqtt_output_requires_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/mqtt-outputs",
        json={"broker_host": "localhost", "topic": "readings"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@requires_mqtt
def test_mqtt_output_appears_in_outputs_aggregate(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/mqtt-outputs"

    created = client.post(
        base, json={"broker_host": "localhost", "topic": "readings"}, headers=auth_headers
    ).json()

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    assert any(o["type"] == "mqtt" for o in resp.json())

    client.delete(f"{base}/{created['id']}", headers=auth_headers)


def test_broker_port_out_of_range_rejected(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/mqtt-outputs"

    resp = client.post(
        base,
        json={"broker_host": "localhost", "broker_port": 0, "topic": "readings"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
