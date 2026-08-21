"""Cross-entity formula/rule/event-trigger references: a field on one
entity can reference `TargetEntity.field` for an entity connected by a
Relationship — see app.services.expressions (the ast.Attribute handling)
and app.services.generator (relationship_lookup / cross_entity_context).
Only works from project-wide generation, never single-entity generation —
covered explicitly below.
"""


def _create_project(client, headers, name="Shop"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


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
                "order": 0,
                "required": True,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "discount_rate",
                "field_type": "float",
                "order": 1,
                "required": True,
                "nullable": False,
                "min_value": 0.05,
                "max_value": 0.5,
            },
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
                "order": 0,
                "required": True,
                "nullable": False,
            },
            {
                "name": "price",
                "field_type": "float",
                "order": 1,
                "required": True,
                "nullable": False,
                "min_value": 10,
                "max_value": 100,
            },
        ],
    )
    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order_id,
            "source_field_id": order_fields["customer_ref"],
            "target_entity_id": customer_id,
            "target_field_id": customer_fields["customer_id"],
        },
        headers=headers,
    )
    return customer_id, customer_fields, order_id, order_fields


def test_formula_references_the_specific_linked_related_row(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields, order_id, order_fields = _setup_customer_order(
        client, auth_headers, project_id
    )

    formula_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order_id}/fields",
        json={
            "name": "discount",
            "field_type": "float",
            "order": 2,
            "required": True,
            "nullable": False,
            "formula": "price * Customer.discount_rate",
        },
        headers=auth_headers,
    )
    assert formula_field.status_code == 201

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"counts": {customer_id: 5, order_id: 30}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    rate_by_customer_id = {row["customer_id"]: row["discount_rate"] for row in data["Customer"]}
    for order in data["Order"]:
        expected_rate = rate_by_customer_id[order["customer_ref"]]
        assert round(order["discount"], 6) == round(order["price"] * expected_rate, 6)


def test_rule_references_related_entity_field(client, auth_headers):
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
                "order": 0,
                "required": True,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "tier",
                "field_type": "enum",
                "order": 1,
                "required": True,
                "nullable": False,
                "enum_values": ["gold"],
            },
        ],
    )
    order_id, order_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Order",
        [
            {
                "name": "customer_ref",
                "field_type": "uuid",
                "order": 0,
                "required": True,
                "nullable": False,
            }
        ],
    )
    client.post(
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

    rule = client.post(
        f"/api/v1/projects/{project_id}/entities/{order_id}/rules",
        json={"condition": 'Customer.tier == "gold"'},
        headers=auth_headers,
    )
    assert rule.status_code == 201

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"counts": {customer_id: 3, order_id: 10}},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_event_trigger_references_related_entity_field(client, auth_headers):
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
                "order": 0,
                "required": True,
                "nullable": False,
                "unique": True,
            },
            {
                "name": "risk_score",
                "field_type": "integer",
                "order": 1,
                "required": True,
                "nullable": False,
                "min_value": 100,
                "max_value": 100,
            },
        ],
    )
    order_id, order_fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Order",
        [
            {
                "name": "customer_ref",
                "field_type": "uuid",
                "order": 0,
                "required": True,
                "nullable": False,
            }
        ],
    )
    client.post(
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

    trigger = client.post(
        f"/api/v1/projects/{project_id}/entities/{order_id}/event-triggers",
        json={"label": "high_risk", "condition": "Customer.risk_score > 50"},
        headers=auth_headers,
    )
    assert trigger.status_code == 201

    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"counts": {customer_id: 2, order_id: 5}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    orders = resp.json()["Order"]
    assert all(row["_triggered_events"] == ["high_risk"] for row in orders)


def test_formula_referencing_nonexistent_related_entity_rejected(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, fields = _create_entity_with_fields(
        client,
        auth_headers,
        project_id,
        "Order",
        [{"name": "price", "field_type": "float", "required": True, "nullable": False}],
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json={
            "name": "discount",
            "field_type": "float",
            "required": True,
            "nullable": False,
            "formula": "price * Customer.discount_rate",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_cross_entity_formula_fails_cleanly_in_single_entity_generate(client, auth_headers):
    """No other entity's data exists outside project-wide generation, so a
    cross-entity reference can't resolve there — a clear 400, not a crash
    or silently wrong value."""
    project_id = _create_project(client, auth_headers)
    customer_id, customer_fields, order_id, order_fields = _setup_customer_order(
        client, auth_headers, project_id
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order_id}/fields",
        json={
            "name": "discount",
            "field_type": "float",
            "order": 2,
            "required": True,
            "nullable": False,
            "formula": "price * Customer.discount_rate",
        },
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{order_id}/generate",
        json={"count": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Customer" in resp.json()["detail"]
