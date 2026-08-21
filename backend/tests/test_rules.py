def _create_project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Sensors"}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Reading"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_rule_filters_generated_rows(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "temperature",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
        },
        headers=auth_headers,
    )

    rule_resp = client.post(
        f"{base}/rules", json={"condition": "temperature > 60"}, headers=auth_headers
    )
    assert rule_resp.status_code == 201

    listed = client.get(f"{base}/rules", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    resp = client.post(f"{base}/generate", json={"count": 15}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 15
    assert all(row["temperature"] > 60 for row in rows)


def test_rule_rejected_when_referencing_unknown_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(f"{base}/rules", json={"condition": "nonexistent > 0"}, headers=auth_headers)
    assert resp.status_code == 400


def test_contradictory_rules_fail_generation_cleanly(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "temperature",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": 0,
            "max_value": 10,
        },
        headers=auth_headers,
    )
    client.post(f"{base}/rules", json={"condition": "temperature > 60"}, headers=auth_headers)

    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 400


def test_delete_rule(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    rule = client.post(f"{base}/rules", json={"condition": "1 > 0"}, headers=auth_headers).json()

    deleted = client.delete(f"{base}/rules/{rule['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(f"{base}/rules", headers=auth_headers)
    assert listed.json() == []
