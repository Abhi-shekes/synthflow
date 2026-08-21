from app.models.field import LogPreset


def _create_project(client, headers, name="Observability"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="LogLine"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_nginx_access_log_preset_looks_like_a_log_line(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "line",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "nginx_access_log",
        },
        headers=auth_headers,
    )
    assert field.status_code == 201
    assert field.json()["preset"] == "nginx_access_log"

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    lines = [row["line"] for row in gen.json()]
    assert all("HTTP/1.1" in line for line in lines)


def test_failed_login_preset_looks_like_a_security_event(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "line",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "failed_login",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    lines = [row["line"] for row in gen.json()]
    assert all("Failed login attempt" in line for line in lines)


def test_every_preset_generates_a_non_empty_line(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    for preset in LogPreset:
        entity_id = _create_entity(client, auth_headers, project_id, name=f"Entity-{preset}")
        base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
        client.post(
            f"{base}/fields",
            json={
                "name": "line",
                "field_type": "string",
                "required": True,
                "nullable": False,
                "preset": preset.value,
            },
            headers=auth_headers,
        )
        gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
        assert gen.status_code == 200, preset
        lines = [row["line"] for row in gen.json()]
        assert all(isinstance(line, str) and line for line in lines), preset


def test_preset_only_allowed_on_string_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "line",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "preset": "nginx_access_log",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_preset_and_regex_are_mutually_exclusive(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "line",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "nginx_access_log",
            "regex": "^[A-Z]+$",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_field_can_set_and_clear_preset(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={"name": "line", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    ).json()

    set_resp = client.patch(
        f"{base}/fields/{field['id']}",
        json={"preset": "docker_log"},
        headers=auth_headers,
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["preset"] == "docker_log"

    clear_resp = client.patch(
        f"{base}/fields/{field['id']}",
        json={"preset": None},
        headers=auth_headers,
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["preset"] is None


def test_unique_field_with_preset_generates_distinct_values(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "line",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "unique": True,
            "preset": "port_scan",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert gen.status_code == 200
    lines = [row["line"] for row in gen.json()]
    assert len(set(lines)) == 20
