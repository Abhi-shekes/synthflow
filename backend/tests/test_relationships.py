def _create_project(client, headers):
    resp = client.post("/api/v1/projects", json={"name": "Shop"}, headers=headers)
    return resp.json()["id"]


def _create_entity_with_fields(client, headers, project_id, name, fields):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    field_ids = {}
    for field in fields:
        created = client.post(
            f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
            json=field,
            headers=headers,
        ).json()
        field_ids[field["name"]] = created["id"]
    return entity["id"], field_ids


def _setup_customer_order(client, headers, project_id):
    customer_id, customer_fields = _create_entity_with_fields(
        client,
        headers,
        project_id,
        "Customer",
        [
            {
                "name": "customer_id",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
                "unique": True,
            }
        ],
    )
    order_id, order_fields = _create_entity_with_fields(
        client,
        headers,
        project_id,
        "Order",
        [
            {
                "name": "customer_ref",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
            }
        ],
    )
    return customer_id, customer_fields, order_id, order_fields


def test_create_relationship_and_generate_project(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields, order_id, order_fields = _setup_customer_order(
        client, auth_headers, project_id
    )

    rel = client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order_id,
            "source_field_id": order_fields["customer_ref"],
            "target_entity_id": customer_id,
            "target_field_id": customer_fields["customer_id"],
        },
        headers=auth_headers,
    )
    assert rel.status_code == 201

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"count": 5, "counts": {customer_id: 3, order_id: 20}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["Customer"]) == 3
    assert len(data["Order"]) == 20

    customer_ids = {row["customer_id"] for row in data["Customer"]}
    order_refs = {row["customer_ref"] for row in data["Order"]}
    assert order_refs.issubset(customer_ids)


def test_relationship_rejects_mismatched_field_types(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Customer",
        [{"name": "id_str", "field_type": "string", "required": True, "nullable": False}],
    )
    order_id, order_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Order",
        [{"name": "ref", "field_type": "integer", "required": True, "nullable": False}],
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order_id,
            "source_field_id": order_fields["ref"],
            "target_entity_id": customer_id,
            "target_field_id": customer_fields["id_str"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_relationship_rejects_self_reference(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Employee",
        [{"name": "manager_id", "field_type": "uuid", "required": True, "nullable": False}],
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "parent_child",
            "source_entity_id": entity_id,
            "source_field_id": fields["manager_id"],
            "target_entity_id": entity_id,
            "target_field_id": fields["manager_id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_one_to_one_relationship_uses_unique_fk_without_replacement(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Customer",
        [
            {
                "name": "customer_id",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
                "unique": True,
            }
        ],
    )
    profile_id, profile_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Profile",
        [
            {
                "name": "customer_ref",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
                "unique": True,
            }
        ],
    )
    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_one",
            "source_entity_id": profile_id,
            "source_field_id": profile_fields["customer_ref"],
            "target_entity_id": customer_id,
            "target_field_id": customer_fields["customer_id"],
        },
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"counts": {customer_id: 10, profile_id: 10}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    refs = [row["customer_ref"] for row in data["Profile"]]
    assert len(refs) == len(set(refs))  # no repeats: one-to-one held


def test_one_to_one_relationship_errors_when_not_enough_targets(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Customer",
        [
            {
                "name": "customer_id",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
                "unique": True,
            }
        ],
    )
    profile_id, profile_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Profile",
        [
            {
                "name": "customer_ref",
                "field_type": "uuid",
                "required": True,
                "nullable": False,
                "unique": True,
            }
        ],
    )
    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_one",
            "source_entity_id": profile_id,
            "source_field_id": profile_fields["customer_ref"],
            "target_entity_id": customer_id,
            "target_field_id": customer_fields["customer_id"],
        },
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"counts": {customer_id: 3, profile_id: 10}},
        headers=auth_headers,
    )
    assert resp.status_code == 400
