import math


def _create_project(client, headers, name="Metrics"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_numeric_field(
    client, headers, project_id, name="Reading", field_type="float"
):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={
            "name": "value",
            "field_type": field_type,
            "required": True,
            "nullable": False,
        },
        headers=headers,
    ).json()
    return entity["id"], field["id"]


def test_linear_trend_matches_formula_exactly(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    created = client.post(
        f"{base}/trends",
        json={"field_id": field_id, "trend_type": "linear", "params": {"start": 10, "slope": 2}},
        headers=auth_headers,
    )
    assert created.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert values == [10 + 2 * i for i in range(10)]


def test_random_walk_stays_within_step_bounds(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/trends",
        json={
            "field_id": field_id,
            "trend_type": "random_walk",
            "params": {"start": 100, "step_size": 1},
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 50}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert values[0] == 100
    for a, b in zip(values, values[1:], strict=False):
        assert abs(b - a) <= 1.0001  # float rounding slack


def test_seasonal_trend_oscillates(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/trends",
        json={
            "field_id": field_id,
            "trend_type": "seasonal",
            "params": {"base": 50, "amplitude": 10, "period": 4},
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 4}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    expected = [
        round(50 + 10 * math.sin(2 * math.pi * i / 4), 2) for i in range(4)
    ]
    assert values == expected


def test_trend_resets_position_each_generate_call(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/trends",
        json={"field_id": field_id, "trend_type": "linear", "params": {"start": 0, "slope": 1}},
        headers=auth_headers,
    )

    first = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers).json()
    second = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers).json()
    assert [r["value"] for r in first] == [r["value"] for r in second] == [0, 1, 2, 3, 4]


def test_trend_only_allowed_on_numeric_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Row"}, headers=auth_headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "name", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/trends",
        json={"field_id": field["id"], "trend_type": "linear", "params": {"start": 0, "slope": 1}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_trend_rejects_missing_params(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/trends",
        json={"field_id": field_id, "trend_type": "linear", "params": {"start": 0}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_trend_rejects_unknown_params(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/trends",
        json={
            "field_id": field_id,
            "trend_type": "linear",
            "params": {"start": 0, "slope": 1, "bogus": 5},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_only_one_trend_per_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    payload = {"field_id": field_id, "trend_type": "linear", "params": {"start": 0, "slope": 1}}
    first = client.post(f"{base}/trends", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = client.post(f"{base}/trends", json=payload, headers=auth_headers)
    assert second.status_code == 400


def test_delete_trend(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    trend = client.post(
        f"{base}/trends",
        json={"field_id": field_id, "trend_type": "linear", "params": {"start": 0, "slope": 1}},
        headers=auth_headers,
    ).json()

    deleted = client.delete(f"{base}/trends/{trend['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(f"{base}/trends", headers=auth_headers)
    assert listed.json() == []


def test_integer_trend_rounds_to_whole_numbers(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_numeric_field(
        client, auth_headers, project_id, field_type="integer"
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/trends",
        json={
            "field_id": field_id,
            "trend_type": "linear",
            "params": {"start": 0, "slope": 0.5},
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 6}, headers=auth_headers)
    values = [row["value"] for row in gen.json()]
    assert all(isinstance(v, int) for v in values)
