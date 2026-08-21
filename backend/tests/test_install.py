"""Modular-installation coverage: runtime feature detection, the API's
graceful degradation when an optional extra is absent, and the
`synthflow init` wizard that writes .env.

These tests must pass on *any* install, whether or not the kafka/mqtt
extras happen to be present — that's the whole point of the feature — so
availability is monkeypatched rather than assumed either way.
"""

import pytest

from app.cli import init, main
from app.services import install


def _create_project(client, headers, name="Install"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(client, headers, project_id, name="Reading"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "v", "field_type": "integer", "required": True, "nullable": False},
        headers=headers,
    )
    return entity["id"]


# --------------------------------------------------------------- detection


def test_describe_reports_every_optional_feature():
    described = {feature["key"]: feature for feature in install.describe()}
    assert set(described) == {"kafka", "mqtt"}
    for feature in described.values():
        assert isinstance(feature["available"], bool)
        assert feature["label"] and feature["description"] and feature["extra"]


def test_is_available_rejects_an_unknown_feature():
    with pytest.raises(ValueError):
        install.is_available("not_a_feature")


def test_require_is_silent_when_available(monkeypatch):
    monkeypatch.setattr(install, "is_available", lambda key: True)
    install.require("kafka")  # must not raise


def test_require_names_the_extra_to_install(monkeypatch):
    monkeypatch.setattr(install, "is_available", lambda key: False)
    with pytest.raises(ValueError) as excinfo:
        install.require("mqtt")
    message = str(excinfo.value)
    assert "mqtt" in message
    # An actionable message, not just "unavailable".
    assert "pip install" in message


def test_detection_does_not_import_the_module(monkeypatch):
    """find_spec, not import — this runs per request, and importing
    aiokafka for real is slow enough to matter."""
    import importlib

    called = []
    real_import_module = importlib.import_module

    def spy(name, *args, **kwargs):
        called.append(name)
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", spy)
    install.is_available("kafka")
    assert "aiokafka" not in called


# ------------------------------------------------------------------- API


def test_install_config_route_lists_features(client, auth_headers):
    resp = client.get("/api/v1/install-config", headers=auth_headers)
    assert resp.status_code == 200
    keys = {feature["key"] for feature in resp.json()}
    assert keys == {"kafka", "mqtt"}


def test_install_config_route_requires_auth(client):
    assert client.get("/api/v1/install-config").status_code == 401


def test_creating_an_output_for_a_missing_extra_fails_cleanly(client, auth_headers, monkeypatch):
    """A 400 naming the fix, not a 500 and not a background task that
    dies on its first tick."""
    monkeypatch.setattr(install, "is_available", lambda key: False)

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/kafka-outputs",
        json={"bootstrap_servers": "localhost:9092", "topic": "t"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "kafka" in resp.json()["detail"]


def test_missing_extra_check_runs_for_mqtt_too(client, auth_headers, monkeypatch):
    monkeypatch.setattr(install, "is_available", lambda key: False)

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/mqtt-outputs",
        json={"broker_host": "localhost", "broker_port": 1883, "topic": "t"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "mqtt" in resp.json()["detail"]


# ------------------------------------------------------------------- CLI


def _env(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path / ".env"


def test_init_writes_selected_profiles_and_extras(tmp_path, capsys):
    env_path = _env(tmp_path)
    code = init(["--services", "kafka,monitoring", "--yes", "--path", str(tmp_path)])
    assert code == 0

    written = env_path.read_text()
    assert "COMPOSE_PROFILES=kafka,monitoring" in written
    # monitoring adds no Python extra, so only kafka appears here.
    assert "SYNTHFLOW_EXTRAS=kafka" in written


def test_init_with_none_selects_core_only(tmp_path):
    env_path = _env(tmp_path)
    assert init(["--none", "--yes", "--path", str(tmp_path)]) == 0

    written = env_path.read_text()
    assert "COMPOSE_PROFILES=\n" in written
    assert "SYNTHFLOW_EXTRAS=\n" in written


def test_init_all_selects_everything(tmp_path):
    env_path = _env(tmp_path)
    assert init(["--all", "--yes", "--path", str(tmp_path)]) == 0

    written = env_path.read_text()
    assert "COMPOSE_PROFILES=kafka,mqtt,monitoring" in written
    assert "SYNTHFLOW_EXTRAS=kafka,mqtt" in written


def test_init_preserves_unrelated_env_entries(tmp_path):
    """Re-running the wizard must not eat someone's SECRET_KEY."""
    env_path = _env(tmp_path)
    env_path.write_text("SECRET_KEY=keep-me\nCOMPOSE_PROFILES=stale\n")

    assert init(["--services", "mqtt", "--yes", "--path", str(tmp_path)]) == 0

    written = env_path.read_text()
    assert "SECRET_KEY=keep-me" in written
    assert "COMPOSE_PROFILES=mqtt" in written
    assert "stale" not in written


def test_init_is_idempotent(tmp_path):
    env_path = _env(tmp_path)
    init(["--services", "kafka", "--yes", "--path", str(tmp_path)])
    once = env_path.read_text()
    init(["--services", "kafka", "--yes", "--path", str(tmp_path)])
    assert env_path.read_text() == once


def test_init_rejects_an_unknown_service(tmp_path):
    _env(tmp_path)
    with pytest.raises(SystemExit):
        init(["--services", "rabbitmq", "--yes", "--path", str(tmp_path)])


def test_init_rejects_conflicting_selection_flags(tmp_path):
    _env(tmp_path)
    with pytest.raises(SystemExit):
        init(["--all", "--none", "--yes", "--path", str(tmp_path)])


def test_init_finds_the_repo_root_from_a_subdirectory(tmp_path):
    """Someone will run this from backend/ — it should still land the
    .env next to docker-compose.yml."""
    env_path = _env(tmp_path)
    nested = tmp_path / "backend"
    nested.mkdir()

    assert init(["--services", "kafka", "--yes", "--path", str(nested)]) == 0
    assert env_path.is_file()
    assert not (nested / ".env").exists()


def test_main_dispatches_init(tmp_path):
    _env(tmp_path)
    assert main(["init", "--none", "--yes", "--path", str(tmp_path)]) == 0


def test_main_without_a_subcommand_prints_usage(capsys):
    assert main([]) == 0
    assert "synthflow init" in capsys.readouterr().out
