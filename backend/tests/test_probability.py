from collections import Counter


def _create_project(client, headers, name="Browsers"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Visit"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_weighted_enum_never_produces_a_zero_weight_value(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["chrome", "firefox", "edge"],
            "enum_weights": [1, 0, 0],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 50}, headers=auth_headers)
    assert gen.status_code == 200
    values = {row["browser"] for row in gen.json()}
    assert values == {"chrome"}


def test_weighted_enum_skews_distribution(client, auth_headers):
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
            "enum_weights": [95, 5],
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 200}, headers=auth_headers)
    counts = Counter(row["browser"] for row in gen.json())
    # Not a precise statistical assertion — just confirms the skew is real and
    # in the right direction, generously bounded to avoid a flaky test.
    assert counts["chrome"] > counts["firefox"] * 3


def test_unweighted_enum_still_uniform_by_default(client, auth_headers):
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

    gen = client.post(f"{base}/generate", json={"count": 30}, headers=auth_headers)
    values = {row["browser"] for row in gen.json()}
    assert values == {"chrome", "firefox"}  # both appear given 30 draws at ~50/50


def test_enum_weights_length_must_match_enum_values(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "enum_values": ["chrome", "firefox", "edge"],
            "enum_weights": [1, 1],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_enum_weights_rejects_negative(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "enum_values": ["chrome", "firefox"],
            "enum_weights": [1, -1],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_enum_weights_rejects_all_zero(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "enum_values": ["chrome", "firefox"],
            "enum_weights": [0, 0],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_enum_weights_rejected_on_non_enum_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={"name": "count", "field_type": "integer", "enum_weights": [1, 2]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_field_can_add_weights_after_creation(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "browser",
            "field_type": "enum",
            "required": True,
            "nullable": False,
            "enum_values": ["chrome", "firefox"],
        },
        headers=auth_headers,
    ).json()

    updated = client.patch(
        f"{base}/fields/{field['id']}", json={"enum_weights": [9, 1]}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["enum_weights"] == [9, 1]

    # Mismatched-length update against the field's existing enum_values.
    bad = client.patch(
        f"{base}/fields/{field['id']}", json={"enum_weights": [1, 2, 3]}, headers=auth_headers
    )
    assert bad.status_code == 400
