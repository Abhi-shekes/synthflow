"""API-behavior simulation (status code mixes, latency, timeouts) turned out
to need almost no new machinery. These tests cover
the one real gap that got closed (numeric-looking enum values generating as
real ints/floats, not strings) and confirm the already-existing pieces
(weighted enums, min/max numeric fields, error injection) compose the way
intended.
"""


def _create_project(client, headers, name="API Testing"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Response"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_numeric_enum_values_generate_as_real_integers(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "status_code",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["200", "404", "500"],
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert gen.status_code == 200
    values = [row["status_code"] for row in gen.json()]
    assert all(isinstance(v, int) for v in values)
    assert set(values) <= {200, 404, 500}


def test_float_looking_enum_values_generate_as_real_floats(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "score",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["1.5", "2.75"],
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["score"] for row in gen.json()]
    assert all(isinstance(v, float) for v in values)


def test_non_numeric_enum_values_remain_strings(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["chrome", "firefox"],
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    values = [row["browser"] for row in gen.json()]
    assert all(isinstance(v, str) for v in values)


def test_weighted_status_code_mix_skews_toward_success(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "status_code",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["200", "404", "500"],
            "enum_weights": [90, 5, 5],
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 200}, headers=auth_headers)
    values = [row["status_code"] for row in gen.json()]
    success_ratio = values.count(200) / len(values)
    assert success_ratio > 0.7


def test_latency_field_with_out_of_range_timeouts(client, auth_headers):
    """Latency is just a FLOAT field with min/max; a "timeout" is an
    out_of_range error injection pushing latency past the max — both
    already-existing engines, composed for the API-behavior use case."""
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "latency_ms",
            "field_type": "float",
            "required": True,
            "nullable": False,
            "min_value": 10,
            "max_value": 500,
        },
        headers=auth_headers,
    ).json()

    client.post(
        f"{base}/error-injections",
        json={"field_id": field["id"], "rate": 1, "error_types": ["out_of_range"]},
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    values = [row["latency_ms"] for row in gen.json()]
    assert all(v < 10 or v > 500 for v in values)
