"""Phase 14 — project version history, diff and rollback.

The payload is a `ProjectTemplate`, the same serialisation export and import
already use. That reuse is why this needed one table rather than a parallel
schema that would drift from the real one.
"""


def _project(client, headers, name="Versioned"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _entity(client, headers, project_id, name):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def _field(client, headers, project_id, entity_id, name, **extra):
    payload = {
        "name": name,
        "field_type": "string",
        "required": True,
        "nullable": False,
        **extra,
    }
    return client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json=payload,
        headers=headers,
    ).json()["id"]


def _snapshot(client, headers, project_id, label=None):
    response = client.post(
        f"/api/v1/projects/{project_id}/versions",
        json={"label": label},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _diff(client, headers, project_id, version, against=None):
    url = f"/api/v1/projects/{project_id}/versions/{version}/diff"
    if against is not None:
        url += f"?against={against}"
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Snapshots
# --------------------------------------------------------------------------


def test_a_snapshot_captures_the_design_and_numbers_itself(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    _field(client, auth_headers, project_id, entity_id, "email")

    first = _snapshot(client, auth_headers, project_id, label="initial")
    assert first["version"] == 1
    assert first["label"] == "initial"
    assert first["created_by_email"] == "user@example.com"

    second = _snapshot(client, auth_headers, project_id)
    assert second["version"] == 2

    detail = client.get(f"/api/v1/projects/{project_id}/versions/1", headers=auth_headers).json()
    assert [e["name"] for e in detail["template"]["entities"]] == ["Customer"]
    assert [f["name"] for f in detail["template"]["entities"][0]["fields"]] == ["email"]


def test_the_list_is_newest_first_and_carries_no_payload(client, auth_headers):
    """A list of twenty versions should not ship twenty full designs to
    render twenty rows."""
    project_id = _project(client, auth_headers)
    for i in range(3):
        _snapshot(client, auth_headers, project_id, label=f"v{i}")

    listed = client.get(f"/api/v1/projects/{project_id}/versions", headers=auth_headers).json()
    assert [v["version"] for v in listed] == [3, 2, 1]
    assert "template" not in listed[0]


def test_a_deleted_version_does_not_free_its_number(client, auth_headers):
    """A version somebody referred to last week must not come back meaning
    something else."""
    project_id = _project(client, auth_headers)
    _snapshot(client, auth_headers, project_id)
    _snapshot(client, auth_headers, project_id)

    assert (
        client.delete(f"/api/v1/projects/{project_id}/versions/2", headers=auth_headers).status_code
        == 204
    )
    assert _snapshot(client, auth_headers, project_id)["version"] == 3


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------


def test_a_diff_against_now_reports_what_changed(client, auth_headers):
    project_id = _project(client, auth_headers)
    customer = _entity(client, auth_headers, project_id, "Customer")
    _field(client, auth_headers, project_id, customer, "email")
    _field(client, auth_headers, project_id, customer, "doomed")
    _snapshot(client, auth_headers, project_id)

    # Change three things: add an entity, add a field, remove a field.
    _entity(client, auth_headers, project_id, "Order")
    _field(client, auth_headers, project_id, customer, "city")
    fields = client.get(
        f"/api/v1/projects/{project_id}/entities/{customer}", headers=auth_headers
    ).json()["fields"]
    doomed = next(f for f in fields if f["name"] == "doomed")
    client.delete(
        f"/api/v1/projects/{project_id}/entities/{customer}/fields/{doomed['id']}",
        headers=auth_headers,
    )

    result = _diff(client, auth_headers, project_id, 1)
    assert result["identical"] is False
    assert result["entities_added"] == ["Order"]
    assert result["entities_removed"] == []
    changed = next(e for e in result["entities_changed"] if e["name"] == "Customer")
    assert changed["fields_added"] == ["city"]
    assert changed["fields_removed"] == ["doomed"]


def test_an_unchanged_project_diffs_to_nothing(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    _field(client, auth_headers, project_id, entity_id, "email")
    _snapshot(client, auth_headers, project_id)

    result = _diff(client, auth_headers, project_id, 1)
    assert result["identical"] is True
    assert result["entities_changed"] == []


def test_a_field_attribute_change_is_reported_with_both_values(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    field_id = _field(client, auth_headers, project_id, entity_id, "email")
    _snapshot(client, auth_headers, project_id)

    client.patch(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields/{field_id}",
        json={"nullable": True, "required": False},
        headers=auth_headers,
    )

    result = _diff(client, auth_headers, project_id, 1)
    changed = result["entities_changed"][0]["fields_changed"][0]
    assert changed["name"] == "email"
    assert changed["changes"]["nullable"] == {"before": False, "after": True}


def test_reordering_fields_is_not_reported_as_a_change(client, auth_headers):
    """`order` shifts whenever a field is inserted above another, and
    reporting that as a change to every field below it would bury the one
    edit somebody actually made."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    first = _field(client, auth_headers, project_id, entity_id, "a")
    _field(client, auth_headers, project_id, entity_id, "b")
    _snapshot(client, auth_headers, project_id)

    client.patch(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields/{first}",
        json={"order": 99},
        headers=auth_headers,
    )

    result = _diff(client, auth_headers, project_id, 1)
    assert result["entities_changed"] == []


def test_two_stored_versions_can_be_compared(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id, "Customer")
    _snapshot(client, auth_headers, project_id)
    _entity(client, auth_headers, project_id, "Order")
    _snapshot(client, auth_headers, project_id)

    result = _diff(client, auth_headers, project_id, 1, against=2)
    assert result["from_version"] == 1
    assert result["to_version"] == 2
    assert result["entities_added"] == ["Order"]


# --------------------------------------------------------------------------
# Rollback
# --------------------------------------------------------------------------


def test_a_rollback_restores_the_design(client, auth_headers):
    project_id = _project(client, auth_headers)
    customer = _entity(client, auth_headers, project_id, "Customer")
    _field(client, auth_headers, project_id, customer, "email")
    _snapshot(client, auth_headers, project_id, label="good")

    _entity(client, auth_headers, project_id, "Regrettable")
    _field(client, auth_headers, project_id, customer, "oops")

    response = client.post(
        f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["restored_from"] == 1

    entities = client.get(f"/api/v1/projects/{project_id}/entities", headers=auth_headers).json()
    assert [e["name"] for e in entities] == ["Customer"]
    assert [f["name"] for f in entities[0]["fields"]] == ["email"]


def test_a_rollback_snapshots_the_state_it_replaced(client, auth_headers):
    """Rolling back is the moment you most want a way back, and asking
    someone to have snapshotted first is asking them to have predicted their
    own mistake."""
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id, "Customer")
    _snapshot(client, auth_headers, project_id)
    _entity(client, auth_headers, project_id, "Order")

    result = client.post(
        f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers
    ).json()
    backup = result["backup_version"]

    # The rollback is itself undoable.
    client.post(
        f"/api/v1/projects/{project_id}/versions/{backup}/rollback",
        json={},
        headers=auth_headers,
    )
    entities = client.get(f"/api/v1/projects/{project_id}/entities", headers=auth_headers).json()
    assert sorted(e["name"] for e in entities) == ["Customer", "Order"]


def test_the_project_row_itself_survives_a_rollback(client, auth_headers):
    """You are rolling back the design, not replacing the project — its id,
    owner and history stay put."""
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id, "Customer")
    _snapshot(client, auth_headers, project_id)
    _entity(client, auth_headers, project_id, "Order")

    client.post(f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers)
    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert project.status_code == 200
    assert project.json()["id"] == project_id


def test_a_rollback_refuses_to_destroy_stored_records_by_accident(client, auth_headers):
    """A record store hangs off an entity with ON DELETE CASCADE, so the
    populations would go with the rebuild. Losing generated data as a side
    effect of reverting a schema is not something to discover afterwards."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id", field_type="uuid")
    _snapshot(client, auth_headers, project_id)

    store_id = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": "default", "identity_field_id": identity},
        headers=auth_headers,
    ).json()["id"]
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/generate",
        json={"count": 5},
        headers=auth_headers,
    )

    refused = client.post(
        f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers
    )
    assert refused.status_code == 409
    assert "Customer" in refused.json()["detail"]

    allowed = client.post(
        f"/api/v1/projects/{project_id}/versions/1/rollback",
        json={"discard_record_stores": True},
        headers=auth_headers,
    )
    assert allowed.status_code == 200


def test_an_empty_store_does_not_block_a_rollback(client, auth_headers):
    """An empty store is a configuration a rollback can cost you; a
    populated one is data."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id", field_type="uuid")
    _snapshot(client, auth_headers, project_id)
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": "default", "identity_field_id": identity},
        headers=auth_headers,
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers
    )
    assert response.status_code == 200


def test_an_unknown_version_is_a_404(client, auth_headers):
    project_id = _project(client, auth_headers)
    assert (
        client.get(f"/api/v1/projects/{project_id}/versions/9", headers=auth_headers).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/versions/9/rollback", json={}, headers=auth_headers
        ).status_code
        == 404
    )


def test_a_viewer_may_read_versions_but_not_snapshot_or_roll_back(client, auth_headers):
    project_id = _project(client, auth_headers)
    _entity(client, auth_headers, project_id, "Customer")
    _snapshot(client, auth_headers, project_id)

    client.post(
        "/api/v1/auth/signup",
        json={"email": "viewer@example.com", "password": "testpassword123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": "testpassword123"},
    ).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}
    org_id = client.post(
        "/api/v1/organizations", json={"name": "Acme"}, headers=auth_headers
    ).json()["id"]
    client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"email": "viewer@example.com", "role": "viewer"},
        headers=auth_headers,
    )
    client.put(
        f"/api/v1/projects/{project_id}/organization",
        json={"organization_id": org_id},
        headers=auth_headers,
    )

    assert client.get(f"/api/v1/projects/{project_id}/versions", headers=viewer).status_code == 200
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/versions", json={"label": "x"}, headers=viewer
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=viewer
        ).status_code
        == 403
    )
