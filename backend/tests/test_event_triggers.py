def _create_project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Sensors"}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Reading"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def _add_temperature_field(client, headers, base, min_value=0, max_value=100):
    client.post(
        f"{base}/fields",
        json={
            "name": "temperature",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": min_value,
            "max_value": max_value,
        },
        headers=headers,
    )


def test_event_trigger_annotates_every_matching_row(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    _add_temperature_field(client, auth_headers, base, min_value=90, max_value=100)

    created = client.post(
        f"{base}/event-triggers",
        json={"label": "high_temperature", "condition": "temperature > 60"},
        headers=auth_headers,
    )
    assert created.status_code == 201

    resp = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 10
    assert all(row["_triggered_events"] == ["high_temperature"] for row in rows)


def test_event_trigger_does_not_reject_non_matching_rows(client, auth_headers):
    """The key semantic difference from a Rule: a trigger that never matches
    still lets generation succeed — it annotates, it doesn't filter."""
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    _add_temperature_field(client, auth_headers, base, min_value=0, max_value=10)

    client.post(
        f"{base}/event-triggers",
        json={"label": "high_temperature", "condition": "temperature > 60"},
        headers=auth_headers,
    )

    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 5
    assert all(row["_triggered_events"] == [] for row in rows)


def test_no_triggered_events_key_without_any_trigger_configured(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    _add_temperature_field(client, auth_headers, base)

    resp = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert all("_triggered_events" not in row for row in rows)


def test_multiple_triggers_can_both_match_same_row(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    _add_temperature_field(client, auth_headers, base, min_value=90, max_value=100)

    client.post(
        f"{base}/event-triggers",
        json={"label": "warm", "condition": "temperature > 50"},
        headers=auth_headers,
    )
    client.post(
        f"{base}/event-triggers",
        json={"label": "hot", "condition": "temperature > 80"},
        headers=auth_headers,
    )

    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert all(row["_triggered_events"] == ["warm", "hot"] for row in rows)


def test_event_trigger_rejected_when_referencing_unknown_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/event-triggers",
        json={"label": "bad", "condition": "nonexistent > 0"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_delete_event_trigger(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    trigger = client.post(
        f"{base}/event-triggers",
        json={"label": "always", "condition": "1 > 0"},
        headers=auth_headers,
    ).json()

    deleted = client.delete(f"{base}/event-triggers/{trigger['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(f"{base}/event-triggers", headers=auth_headers)
    assert listed.json() == []
