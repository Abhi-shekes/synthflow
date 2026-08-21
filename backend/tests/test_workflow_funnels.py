"""Covers the funnel-realism additions to Workflow: per-transition `weight`
and per-state `stop_probabilities`, both optional and backward-compatible
(see app.models.workflow — this is what makes a Workflow chain a realistic
stand-in for the roadmap's "user behavior simulation" funnels instead of a
new concept)."""

from collections import Counter


def _create_project(client, headers, name="Funnels"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_stage_field(client, headers, project_id, name="Session"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "stage", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    ).json()
    return entity["id"], field["id"]


FUNNEL = {
    "states": ["landing", "search", "cart", "checkout", "purchase"],
    "initial_states": ["landing"],
    "transitions": [
        {"source": "landing", "target": "search"},
        {"source": "search", "target": "cart"},
        {"source": "cart", "target": "checkout"},
        {"source": "checkout", "target": "purchase"},
    ],
}


def test_stop_probability_forces_dropoff_at_a_specific_stage(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={
            "field_id": field_id,
            **FUNNEL,
            # Never stop at landing, always stop right after search — every
            # session should end at exactly "search", never further.
            "stop_probabilities": {"landing": 0.0, "search": 1.0},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 30}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        assert row["stage"] == "search"
        assert row["stage_history"] == ["landing", "search"]


def test_transition_weight_skews_branch_choice(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/workflows",
        json={
            "field_id": field_id,
            "states": ["start", "likely", "unlikely"],
            "initial_states": ["start"],
            "transitions": [
                {"source": "start", "target": "likely", "weight": 95},
                {"source": "start", "target": "unlikely", "weight": 5},
            ],
            # Force every walk to take exactly one step past "start" so the
            # branch choice, not the stop draw, determines the final state.
            "stop_probabilities": {"start": 0.0, "likely": 1.0, "unlikely": 1.0},
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 300}, headers=auth_headers)
    counts = Counter(row["stage"] for row in gen.json())
    assert counts["likely"] > counts["unlikely"] * 5


def test_stop_probabilities_keys_must_be_valid_states(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={"field_id": field_id, **FUNNEL, "stop_probabilities": {"nonexistent": 0.5}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_stop_probabilities_values_must_be_between_0_and_1(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={"field_id": field_id, **FUNNEL, "stop_probabilities": {"landing": 1.5}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_transition_weight_must_be_positive(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={
            "field_id": field_id,
            "states": ["a", "b"],
            "initial_states": ["a"],
            "transitions": [{"source": "a", "target": "b", "weight": 0}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_workflow_without_weights_or_stop_probabilities_defaults_cleanly(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_stage_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    created = client.post(
        f"{base}/workflows", json={"field_id": field_id, **FUNNEL}, headers=auth_headers
    ).json()
    assert created["stop_probabilities"] is None
    assert all(t["weight"] == 1.0 for t in created["transitions"])
