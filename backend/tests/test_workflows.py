def _create_project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Logistics"}, headers=headers).json()["id"]


def _create_entity_with_status_field(client, headers, project_id, name="Order"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "status", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    ).json()
    return entity["id"], field["id"]


ORDER_WORKFLOW = {
    "states": ["created", "packed", "shipped", "delivered"],
    "initial_states": ["created"],
    "transitions": [
        {"source": "created", "target": "packed"},
        {"source": "packed", "target": "shipped"},
        {"source": "shipped", "target": "delivered"},
    ],
}


def test_create_workflow_and_generate_respects_state_graph(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows", json={"field_id": field_id, **ORDER_WORKFLOW}, headers=auth_headers
    )
    assert resp.status_code == 201

    gen = client.post(f"{base}/generate", json={"count": 30}, headers=auth_headers)
    assert gen.status_code == 200
    rows = gen.json()
    assert len(rows) == 30

    valid_states = set(ORDER_WORKFLOW["states"])
    for row in rows:
        assert row["status"] in valid_states
        history = row["status_history"]
        assert history[0] == "created"  # the only initial state
        assert history[-1] == row["status"]
        # every consecutive pair in the history must be a real transition
        edges = {(t["source"], t["target"]) for t in ORDER_WORKFLOW["transitions"]}
        for a, b in zip(history, history[1:], strict=False):
            assert (a, b) in edges


def test_workflow_field_must_belong_to_entity(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, _ = _create_entity_with_status_field(client, auth_headers, project_id, "Order")
    other_entity_id, other_field_id = _create_entity_with_status_field(
        client, auth_headers, project_id, "Shipment"
    )
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={"field_id": other_field_id, **ORDER_WORKFLOW},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_workflow_initial_states_must_be_subset_of_states(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={
            "field_id": field_id,
            "states": ["created", "packed"],
            "initial_states": ["nonexistent"],
            "transitions": [],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_workflow_transition_must_reference_known_states(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/workflows",
        json={
            "field_id": field_id,
            "states": ["created", "packed"],
            "initial_states": ["created"],
            "transitions": [{"source": "created", "target": "nonexistent"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_only_one_workflow_per_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    first = client.post(
        f"{base}/workflows", json={"field_id": field_id, **ORDER_WORKFLOW}, headers=auth_headers
    )
    assert first.status_code == 201

    second = client.post(
        f"{base}/workflows", json={"field_id": field_id, **ORDER_WORKFLOW}, headers=auth_headers
    )
    assert second.status_code == 400


def test_delete_workflow(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    workflow = client.post(
        f"{base}/workflows", json={"field_id": field_id, **ORDER_WORKFLOW}, headers=auth_headers
    ).json()

    deleted = client.delete(f"{base}/workflows/{workflow['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(f"{base}/workflows", headers=auth_headers)
    assert listed.json() == []


def test_workflow_history_excluded_from_csv(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_status_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    client.post(
        f"{base}/workflows", json={"field_id": field_id, **ORDER_WORKFLOW}, headers=auth_headers
    )

    resp = client.post(f"{base}/generate?format=csv", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 200
    header = resp.text.splitlines()[0]
    assert header == "status"
