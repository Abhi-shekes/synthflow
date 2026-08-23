"""CRUD-level coverage only — no real Kafka broker is available in the
test environment, so these don't assert actual message delivery (that's
covered by live docker-compose verification against a real broker).
Every test that successfully creates an output deletes it
before returning, so its background asyncio.Task (see
app.services.stream_producers) is cancelled promptly rather than left
retrying against a broker that doesn't exist — the app's lifespan
shutdown hook would also catch it at test teardown, but there's no reason
to rely on that as the only safety net.
"""

import pytest

from app.services import install

requires_kafka = pytest.mark.skipif(
    not install.is_available("kafka"),
    reason="optional 'kafka' extra is not installed in this environment",
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


@requires_kafka
def test_create_list_and_delete_kafka_output(client, auth_headers, no_background_producers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/kafka-outputs"

    created = client.post(
        base,
        json={"bootstrap_servers": "localhost:9092", "topic": "readings", "events_per_second": 5},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["topic"] == "readings"
    assert body["events_per_second"] == 5

    listed = client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(f"{base}/{body['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get(base, headers=auth_headers)
    assert listed_after.json() == []


def test_kafka_output_requires_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/kafka-outputs",
        json={"bootstrap_servers": "localhost:9092", "topic": "readings"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@requires_kafka
def test_kafka_output_appears_in_outputs_aggregate(client, auth_headers, no_background_producers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/kafka-outputs"

    created = client.post(
        base,
        json={"bootstrap_servers": "localhost:9092", "topic": "readings"},
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    assert any(o["type"] == "kafka" for o in resp.json())

    client.delete(f"{base}/{created['id']}", headers=auth_headers)


def test_events_per_second_out_of_range_rejected(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/kafka-outputs"

    resp = client.post(
        base,
        json={"bootstrap_servers": "localhost:9092", "topic": "readings", "events_per_second": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422
