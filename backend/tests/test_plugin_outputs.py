"""CRUD-level coverage plus a real background-task delivery test — unlike
Kafka/MQTT (no real broker available in the test environment), a plugin
output's "broker" is just a Python function, so the actual delivery loop
(app.services.plugin_output_producers) can be exercised for real here
with a fake in-memory plugin instead of only covering CRUD. Every test
that successfully creates an output deletes it before returning, so its
background asyncio.Task is cancelled promptly.
"""

import time

import pytest

from app.api.routes import plugin_outputs as plugin_outputs_route
from app.services import plugins


class _FakeDist:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeEntryPoint:
    def __init__(self, name, fn, dist_name="example-plugin"):
        self.name = name
        self._fn = fn
        self.dist = _FakeDist(dist_name)

    def load(self):
        return self._fn


def _fake_entry_points_for_outputs(fake_points):
    def _fake_entry_points(group=None):
        if group == plugins.OUTPUT_PLUGIN_ENTRY_POINT_GROUP:
            return fake_points
        return []

    return _fake_entry_points


@pytest.fixture
def no_background_producer(monkeypatch):
    """Stop `POST /plugin-outputs` from launching a real producer task.

    These tests cover CRUD, not delivery. Letting the producer run makes
    them intermittently fail, and the reason is the test database rather
    than the code: conftest binds every session to ONE SQLite in-memory
    connection via StaticPool. The producer loads its batch on a worker
    thread through its own short-lived session, and that session's
    `close()` returns the shared connection to the pool — which rolls back
    whatever transaction is on it. Land that between a DELETE's commit and
    the next read and the delete is silently undone, which is exactly how
    this surfaced: a 204 followed by the row still being listed.

    Requested explicitly rather than autouse, because
    `test_background_task_actually_delivers_real_generated_rows` needs a
    real producer — and a fixture that silently disabled the thing one
    test exists to check would be worse than the flake.

    Production never hits this; Postgres gives each session its own
    connection.
    """
    monkeypatch.setattr(plugin_outputs_route, "start_plugin_output", lambda output: None)


def _create_project(client, headers, name="PluginOutputs"):
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


def test_create_list_and_delete_plugin_output(
    client, auth_headers, monkeypatch, no_background_producer
):
    fake_point = _FakeEntryPoint("noop", lambda config, rows: None)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/plugin-outputs"

    created = client.post(
        base,
        json={"plugin_name": "noop", "config": {"path": "/tmp/x"}, "events_per_second": 5},
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["plugin_name"] == "noop"
    assert body["config"] == {"path": "/tmp/x"}

    listed = client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(f"{base}/{body['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get(base, headers=auth_headers)
    assert listed_after.json() == []


def test_unknown_plugin_name_is_rejected(client, auth_headers, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/plugin-outputs"

    resp = client.post(base, json={"plugin_name": "totally_made_up"}, headers=auth_headers)
    assert resp.status_code == 400


def test_plugin_output_requires_fields(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("noop", lambda config, rows: None)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Empty"}, headers=auth_headers
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/plugin-outputs",
        json={"plugin_name": "noop"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_plugin_output_appears_in_outputs_aggregate(
    client, auth_headers, monkeypatch, no_background_producer
):
    fake_point = _FakeEntryPoint("noop", lambda config, rows: None)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/plugin-outputs"

    created = client.post(base, json={"plugin_name": "noop"}, headers=auth_headers).json()

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    assert any(o["type"] == "plugin" for o in resp.json())

    client.delete(f"{base}/{created['id']}", headers=auth_headers)


def test_events_per_second_out_of_range_rejected(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("noop", lambda config, rows: None)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/plugin-outputs"

    resp = client.post(
        base, json={"plugin_name": "noop", "events_per_second": 0}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_output_plugins_route_lists_installed_plugins(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("noop", lambda config, rows: None, dist_name="my-output-plugin")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    resp = client.get("/api/v1/output-plugins", headers=auth_headers)
    assert resp.status_code == 200
    by_name = {p["name"]: p for p in resp.json()}
    assert by_name["noop"]["source"] == "plugin:my-output-plugin"


def test_output_plugins_route_requires_auth(client, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([]))
    resp = client.get("/api/v1/output-plugins")
    assert resp.status_code == 401


def test_background_task_actually_delivers_real_generated_rows(client, auth_headers, monkeypatch):
    """The real proof, not just CRUD: a fake plugin records every batch it
    receives, and this waits for the actual background asyncio.Task
    (started by the create route) to deliver at least one batch of real
    generated rows before deleting the output."""
    delivered: list[list[dict]] = []

    def record(config, rows):
        assert config == {"marker": "hello"}
        delivered.append(rows)

    fake_point = _FakeEntryPoint("record", record)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_outputs([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/plugin-outputs"

    created = client.post(
        base,
        json={
            "plugin_name": "record",
            "config": {"marker": "hello"},
            "events_per_second": 20,
            "batch_size": 3,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201

    for _ in range(50):
        if delivered:
            break
        time.sleep(0.05)

    assert delivered, "background task never delivered a batch"
    assert len(delivered[0]) == 3
    for row in delivered[0]:
        assert isinstance(row["temperature"], int)

    client.delete(f"{base}/{created.json()['id']}", headers=auth_headers)
