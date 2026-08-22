from app.models.field import IdentifierPreset, LogPreset, PiiPreset
from app.services import plugins


class _FakeDist:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeEntryPoint:
    def __init__(self, name, fn, dist_name="example-plugin", raise_on_load=False):
        self.name = name
        self._fn = fn
        self._raise_on_load = raise_on_load
        self.dist = _FakeDist(dist_name)

    def load(self):
        if self._raise_on_load:
            raise ImportError("simulated broken plugin")
        return self._fn


def _fake_entry_points_returning(fake_points):
    def _fake_entry_points(group=None):
        assert group == plugins.ENTRY_POINT_GROUP
        return fake_points

    return _fake_entry_points


def _create_project(client, headers, name="Plugins"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Record"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_builtin_presets_are_available_with_no_plugins_installed(monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([]))
    registry = plugins.available_presets()
    assert "pan" in registry
    assert "nginx_access_log" in registry
    assert "person_name" in registry
    # Counted from the enums rather than hardcoded: the previous literal
    # meant adding PiiPreset failed this test for no reason, which says
    # nothing about whether discovery works.
    assert len(registry) == len(LogPreset) + len(IdentifierPreset) + len(PiiPreset)


def test_third_party_plugin_is_discovered_and_generates_values(monkeypatch):
    fake_point = _FakeEntryPoint("shout", lambda: "HELLO")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    registry = plugins.available_presets()
    assert "shout" in registry
    assert registry["shout"]() == "HELLO"
    assert plugins.generate_preset_value("shout") == "HELLO"


def test_plugin_name_colliding_with_a_builtin_preset_is_skipped(monkeypatch):
    fake_point = _FakeEntryPoint("pan", lambda: "NOT-A-REAL-PAN")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    value = plugins.generate_preset_value("pan")
    assert value != "NOT-A-REAL-PAN"
    assert len(value) == 10


def test_plugin_that_fails_to_load_does_not_break_other_presets(monkeypatch):
    broken = _FakeEntryPoint("broken", None, raise_on_load=True)
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([broken]))

    registry = plugins.available_presets()
    assert "broken" not in registry
    assert "pan" in registry


def test_list_available_presets_reports_plugin_source(monkeypatch):
    fake_point = _FakeEntryPoint("shout", lambda: "HELLO", dist_name="my-shout-plugin")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    presets = plugins.list_available_presets()
    by_name = {p["name"]: p for p in presets}
    assert by_name["shout"]["source"] == "plugin:my-shout-plugin"
    assert by_name["shout"]["category"] == "plugin"
    assert by_name["pan"]["source"] == "builtin"
    assert by_name["pan"]["category"] == "identifier"
    assert by_name["nginx_access_log"]["category"] == "log"


def test_generator_plugins_route_lists_builtin_presets(client, auth_headers, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([]))
    resp = client.get("/api/v1/generator-plugins", headers=auth_headers)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert "pan" in names
    assert "failed_login" in names


def test_generator_plugins_route_surfaces_a_discovered_plugin(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("shout", lambda: "HELLO")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    resp = client.get("/api/v1/generator-plugins", headers=auth_headers)
    assert resp.status_code == 200
    by_name = {p["name"]: p for p in resp.json()}
    assert by_name["shout"]["category"] == "plugin"


def test_generator_plugins_route_requires_auth(client, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([]))
    resp = client.get("/api/v1/generator-plugins")
    assert resp.status_code == 401


def test_unknown_preset_is_rejected_when_creating_a_field(client, auth_headers, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([]))
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "value",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "totally_made_up",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_field_can_use_a_third_party_plugin_preset(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("shout", lambda: "HELLO")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "value",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "shout",
        },
        headers=auth_headers,
    )
    assert field.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
    assert gen.status_code == 200
    assert all(row["value"] == "HELLO" for row in gen.json())


def test_generate_fails_cleanly_when_a_fields_plugin_is_later_uninstalled(
    client, auth_headers, monkeypatch
):
    fake_point = _FakeEntryPoint("shout", lambda: "HELLO")
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([fake_point]))

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "value",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "shout",
        },
        headers=auth_headers,
    )
    assert field.status_code == 201

    # Simulate the plugin package being uninstalled: the field still has
    # preset="shout" stored, but the registry no longer resolves it.
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_returning([]))

    gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
    assert gen.status_code == 400
