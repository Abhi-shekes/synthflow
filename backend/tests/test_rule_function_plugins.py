from app.services import expressions, plugins


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


def _fake_entry_points_for_rule_functions(fake_points):
    def _fake_entry_points(group=None):
        if group == plugins.RULE_FUNCTION_ENTRY_POINT_GROUP:
            return fake_points
        return []

    return _fake_entry_points


def _create_project(client, headers, name="RuleFunctions"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Record"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_no_rule_function_plugins_installed_by_default(monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_rule_functions([]))
    assert plugins.available_rule_functions() == {}


def test_builtin_functions_still_work_with_no_plugins(monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_rule_functions([]))
    assert expressions.evaluate("abs(-3)", {}) == 3
    assert expressions.evaluate("max(1, 2, 3)", {}) == 3


def test_a_plugin_function_is_discovered_and_callable_from_an_expression(monkeypatch):
    fake_point = _FakeEntryPoint("double", lambda x: x * 2)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    assert "double" in plugins.available_rule_functions()
    assert expressions.evaluate("double(21)", {}) == 42


def test_a_plugin_function_can_reference_row_variables(monkeypatch):
    fake_point = _FakeEntryPoint("double", lambda x: x * 2)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    assert expressions.evaluate("double(price)", {"price": 10}) == 20


def test_plugin_function_cannot_shadow_a_builtin_name(monkeypatch):
    fake_point = _FakeEntryPoint("abs", lambda x: "NOT-THE-REAL-ABS")
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    assert expressions.evaluate("abs(-5)", {}) == 5


def test_unknown_function_is_still_rejected(monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_rule_functions([]))
    try:
        expressions.evaluate("totally_made_up(1)", {})
        raise AssertionError("expected ExpressionError")
    except expressions.ExpressionError:
        pass


def test_rule_function_that_fails_to_load_does_not_break_others(monkeypatch):
    broken = _FakeEntryPoint("broken", None, raise_on_load=True)
    working = _FakeEntryPoint("double", lambda x: x * 2)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([broken, working])
    )

    registry = plugins.available_rule_functions()
    assert "broken" not in registry
    assert "double" in registry


def test_list_available_rule_functions_reports_plugin_source(monkeypatch):
    fake_point = _FakeEntryPoint("double", lambda x: x * 2, dist_name="my-rule-plugin")
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    functions = plugins.list_available_rule_functions()
    assert functions == [{"name": "double", "source": "plugin:my-rule-plugin"}]


def test_rule_functions_route_lists_builtins(client, auth_headers, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_rule_functions([]))
    resp = client.get("/api/v1/rule-functions", headers=auth_headers)
    assert resp.status_code == 200
    by_name = {f["name"]: f for f in resp.json()}
    assert by_name["noise"]["source"] == "builtin"
    assert by_name["uniform"]["source"] == "builtin"


def test_rule_functions_route_surfaces_a_discovered_plugin(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("double", lambda x: x * 2)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    resp = client.get("/api/v1/rule-functions", headers=auth_headers)
    assert resp.status_code == 200
    by_name = {f["name"]: f for f in resp.json()}
    assert by_name["double"]["source"] == "plugin:example-plugin"


def test_rule_functions_route_requires_auth(client, monkeypatch):
    monkeypatch.setattr(plugins, "entry_points", _fake_entry_points_for_rule_functions([]))
    resp = client.get("/api/v1/rule-functions")
    assert resp.status_code == 401


def test_a_rule_condition_can_call_a_plugin_function(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("always_true", lambda: True)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={"name": "price", "field_type": "float", "required": True, "nullable": False},
        headers=auth_headers,
    )
    rule = client.post(f"{base}/rules", json={"condition": "always_true()"}, headers=auth_headers)
    assert rule.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
    assert gen.status_code == 200
    assert len(gen.json()) == 3


def test_a_formula_can_call_a_plugin_function(client, auth_headers, monkeypatch):
    fake_point = _FakeEntryPoint("double", lambda x: x * 2)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "price",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 100,
        },
        headers=auth_headers,
    )
    formula_field = client.post(
        f"{base}/fields",
        json={
            "name": "double_price",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "formula": "double(price)",
        },
        headers=auth_headers,
    )
    assert formula_field.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        assert row["double_price"] == row["price"] * 2


def test_a_rule_calling_a_date_specific_function_on_a_date_field_validates_cleanly(
    client, auth_headers, monkeypatch
):
    """Regression test: creating a field/rule used to build its condition's
    validation dummy values as `1` for every field regardless of type, so
    a plugin function that only accepts a real date string (like
    is_business_day) would raise a raw, unhandled exception (surfacing as
    a 500) the moment someone tried to use it on a DATE field — even
    though the exact same condition works fine at real generation time,
    when the field actually holds a date string. dummy_row_values now
    picks a type-appropriate stand-in per field."""

    def is_business_day(iso_date: str) -> bool:
        from datetime import date

        return date.fromisoformat(iso_date).weekday() < 5

    fake_point = _FakeEntryPoint("is_business_day", is_business_day)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "order_date",
            "field_type": "date",
            "required": True,
            "nullable": False,
        },
        headers=auth_headers,
    )
    rule = client.post(
        f"{base}/rules",
        json={"condition": "is_business_day(order_date)"},
        headers=auth_headers,
    )
    assert rule.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    assert len(gen.json()) == 10


def test_a_function_that_always_raises_surfaces_as_400_not_500(client, auth_headers, monkeypatch):
    def always_broken(x):
        raise RuntimeError("boom")

    fake_point = _FakeEntryPoint("always_broken", always_broken)
    monkeypatch.setattr(
        plugins, "entry_points", _fake_entry_points_for_rule_functions([fake_point])
    )

    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={"name": "price", "field_type": "float", "required": True, "nullable": False},
        headers=auth_headers,
    )
    resp = client.post(
        f"{base}/rules",
        json={"condition": "always_broken(price)"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
