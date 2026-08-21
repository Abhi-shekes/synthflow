def _create_project(client, headers, name="Pipeline"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(client, headers, project_id, field_payload, entity_name="Record"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": entity_name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json=field_payload,
        headers=headers,
    ).json()
    return entity["id"], field["id"]


def test_null_error_forces_null_values(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    created = client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["null"]},
        headers=auth_headers,
    )
    assert created.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    values = [row["value"] for row in gen.json()]
    assert all(v is None for v in values)


def test_empty_error_on_string_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["empty"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert all(v == "" for v in values)


def test_duplicate_error_repeats_previous_rows_value(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "integer", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["duplicate"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    # Row 0 has no previous row to duplicate, so it keeps its own generated
    # value; every later row copies the row before it, which cascades the
    # first row's value through the whole batch.
    assert all(v == values[0] for v in values[1:])


def test_truncate_error_shortens_string(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {
            "name": "value",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "regex": "^[A-Z]{10}$",
        },
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["truncate"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert all(1 <= len(v) < 10 for v in values)


def test_wrong_type_error_on_integer_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "integer", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["wrong_type"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert all(isinstance(v, str) for v in values)


def test_out_of_range_error_exceeds_bounds(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {
            "name": "value",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
        },
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["out_of_range"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert all(v < 0 or v > 100 for v in values)


def test_error_types_must_be_valid_for_field_type(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "integer", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 0.5, "error_types": ["truncate"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_error_types_cannot_be_empty(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "integer", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 0.5, "error_types": []},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_only_one_error_injection_per_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    payload = {"field_id": field_id, "rate": 0.5, "error_types": ["null"]}
    first = client.post(f"{base}/error-injections", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = client.post(f"{base}/error-injections", json=payload, headers=auth_headers)
    assert second.status_code == 400


def test_field_id_must_belong_to_entity(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, _field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    other_entity_id, other_field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "other", "field_type": "string", "required": True, "nullable": False},
        entity_name="Other",
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/error-injections",
        json={"field_id": other_field_id, "rate": 0.5, "error_types": ["null"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_delete_error_injection(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": False},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    created = client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 0.5, "error_types": ["null"]},
        headers=auth_headers,
    ).json()

    deleted = client.delete(
        f"{base}/error-injections/{created['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204

    listed = client.get(f"{base}/error-injections", headers=auth_headers)
    assert listed.json() == []


def test_rule_can_discard_corrupted_rows(client, auth_headers):
    """Documents the interaction called out in ErrorInjection's docstring: a
    rule evaluates the row *after* corruption, so a rule constraining the
    same field can filter out every corrupted row, and generation fails
    cleanly once the retry budget is exhausted."""
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_field(
        client,
        auth_headers,
        project_id,
        {"name": "value", "field_type": "string", "required": True, "nullable": True},
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/error-injections",
        json={"field_id": field_id, "rate": 1, "error_types": ["null"]},
        headers=auth_headers,
    )
    client.post(
        f"{base}/rules", json={"condition": "value != None"}, headers=auth_headers
    )

    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 400
