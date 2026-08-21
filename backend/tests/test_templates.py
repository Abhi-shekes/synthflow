def _signup(client, email):
    client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorsebattery1"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correcthorsebattery1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_rich_project(client, headers, project_name="Storefront"):
    """A project touching every attachment type export/import needs to
    handle: two related entities, a rule, an event trigger, a workflow, a
    trend, an error injection, a lookup table + attachment, and a geo
    route. Returns (project_id, ids-dict) for assertions."""
    project = client.post("/api/v1/projects", json={"name": project_name}, headers=headers).json()
    project_id = project["id"]

    customer = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Customer"}, headers=headers
    ).json()
    customer_id_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{customer['id']}/fields",
        json={
            "name": "id",
            "field_type": "integer",
            "required": True,
            "nullable": False,
            "unique": True,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{customer['id']}/fields",
        json={"name": "discount_rate", "field_type": "float", "required": True, "nullable": False},
        headers=headers,
    )

    order = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Order"}, headers=headers
    ).json()
    customer_ref_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/fields",
        json={"name": "customer_id", "field_type": "integer", "required": True, "nullable": False},
        headers=headers,
    ).json()
    price_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/fields",
        json={
            "name": "price",
            "field_type": "float",
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 100,
        },
        headers=headers,
    ).json()
    status_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/fields",
        json={"name": "status", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    ).json()
    city_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/fields",
        json={"name": "ship_city", "field_type": "string", "required": True, "nullable": False},
        headers=headers,
    ).json()
    position_field = client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/fields",
        json={"name": "position", "field_type": "object", "required": True, "nullable": False},
        headers=headers,
    ).json()

    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order["id"],
            "source_field_id": customer_ref_field["id"],
            "target_entity_id": customer["id"],
            "target_field_id": customer_id_field["id"],
        },
        headers=headers,
    )

    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/rules",
        json={"condition": "price > 0"},
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/event-triggers",
        json={"label": "high_value", "condition": "price > 90"},
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/workflows",
        json={
            "field_id": status_field["id"],
            "states": ["placed", "shipped", "delivered"],
            "initial_states": ["placed"],
            "transitions": [
                {"source": "placed", "target": "shipped"},
                {"source": "shipped", "target": "delivered"},
            ],
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/trends",
        json={
            "field_id": price_field["id"],
            "trend_type": "linear",
            "params": {"start": 1, "slope": 1},
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/error-injections",
        json={"field_id": customer_ref_field["id"], "rate": 0.1, "error_types": ["null"]},
        headers=headers,
    )

    lookup_table = client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": "Cities"},
        files={"file": ("cities.csv", b"name\nSeattle\nAustin\n", "text/csv")},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/lookup-attachments",
        json={
            "field_id": city_field["id"],
            "lookup_table_id": lookup_table["id"],
            "column": "name",
        },
        headers=headers,
    )

    route_table = client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": "Route"},
        files={"file": ("route.csv", b"lat,lon\n10.0,20.0\n30.0,40.0\n", "text/csv")},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{order['id']}/geo-routes",
        json={
            "field_id": position_field["id"],
            "lookup_table_id": route_table["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=headers,
    )

    return project_id


def test_export_returns_the_full_project_shape(client, auth_headers):
    project_id = _build_rich_project(client, auth_headers)

    resp = client.get(f"/api/v1/projects/{project_id}/export", headers=auth_headers)
    assert resp.status_code == 200
    template = resp.json()

    assert template["name"] == "Storefront"
    entity_names = {e["name"] for e in template["entities"]}
    assert entity_names == {"Customer", "Order"}
    order = next(e for e in template["entities"] if e["name"] == "Order")
    field_names = {f["name"] for f in order["fields"]}
    assert field_names == {"customer_id", "price", "status", "ship_city", "position"}

    assert len(template["relationships"]) == 1
    assert template["relationships"][0] == {
        "relationship_type": "one_to_many",
        "source_entity": "Order",
        "source_field": "customer_id",
        "target_entity": "Customer",
        "target_field": "id",
    }
    assert len(template["rules"]) == 1
    assert template["rules"][0] == {"entity": "Order", "condition": "price > 0"}
    assert len(template["event_triggers"]) == 1
    assert len(template["workflows"]) == 1
    assert template["workflows"][0]["field"] == "status"
    assert len(template["trends"]) == 1
    assert template["trends"][0]["field"] == "price"
    assert len(template["error_injections"]) == 1
    assert len(template["lookup_tables"]) == 2
    cities = next(t for t in template["lookup_tables"] if t["name"] == "Cities")
    assert cities["data"] == [{"name": "Seattle"}, {"name": "Austin"}]
    assert len(template["lookup_attachments"]) == 1
    assert len(template["geo_routes"]) == 1


def test_export_requires_ownership(client, auth_headers):
    project_id = _build_rich_project(client, auth_headers)
    other_headers = _signup(client, "someone-else@example.com")

    resp = client.get(f"/api/v1/projects/{project_id}/export", headers=other_headers)
    assert resp.status_code == 404


def test_import_creates_a_new_project_owned_by_the_importer(client, auth_headers):
    project_id = _build_rich_project(client, auth_headers)
    template = client.get(f"/api/v1/projects/{project_id}/export", headers=auth_headers).json()

    importer_headers = _signup(client, "importer@example.com")
    resp = client.post("/api/v1/projects/import", json=template, headers=importer_headers)
    assert resp.status_code == 201
    imported = resp.json()
    assert imported["name"] == "Storefront"

    owned = client.get("/api/v1/projects", headers=importer_headers).json()
    assert any(p["id"] == imported["id"] for p in owned)

    entities = client.get(
        f"/api/v1/projects/{imported['id']}/entities", headers=importer_headers
    ).json()
    assert {e["name"] for e in entities} == {"Customer", "Order"}


def test_round_tripped_project_generates_working_rows(client, auth_headers):
    project_id = _build_rich_project(client, auth_headers)
    template = client.get(f"/api/v1/projects/{project_id}/export", headers=auth_headers).json()

    imported = client.post("/api/v1/projects/import", json=template, headers=auth_headers).json()

    gen = client.post(
        f"/api/v1/projects/{imported['id']}/generate",
        json={"count": 5, "counts": {}},
        headers=auth_headers,
    )
    assert gen.status_code == 200
    body = gen.json()
    orders = body["Order"]
    assert len(orders) == 5
    for row in orders:
        assert row["price"] > 0
        assert row["status"] in {"placed", "shipped", "delivered"}
        assert row["ship_city"] in {"Seattle", "Austin"}
        assert set(row["position"].keys()) == {"lat", "lon"}


def test_import_rejects_unknown_entity_reference(client, auth_headers):
    template = {
        "name": "Broken",
        "entities": [{"name": "Order", "fields": []}],
        "rules": [{"entity": "NoSuchEntity", "condition": "1 > 0"}],
    }
    resp = client.post("/api/v1/projects/import", json=template, headers=auth_headers)
    assert resp.status_code == 400


def test_import_rejects_unknown_field_reference(client, auth_headers):
    template = {
        "name": "Broken",
        "entities": [{"name": "Order", "fields": []}],
        "trends": [
            {
                "entity": "Order",
                "field": "no_such_field",
                "trend_type": "linear",
                "params": {"start": 0, "slope": 1},
            }
        ],
    }
    resp = client.post("/api/v1/projects/import", json=template, headers=auth_headers)
    assert resp.status_code == 400


def test_import_rejects_invalid_field_type(client, auth_headers):
    template = {
        "name": "Broken",
        "entities": [{"name": "Order", "fields": [{"name": "x", "field_type": "not_a_real_type"}]}],
    }
    resp = client.post("/api/v1/projects/import", json=template, headers=auth_headers)
    assert resp.status_code == 400


def test_failed_import_does_not_create_a_partial_project(client, auth_headers):
    before = len(client.get("/api/v1/projects", headers=auth_headers).json())

    template = {
        "name": "Broken",
        "entities": [{"name": "Order", "fields": []}],
        "rules": [{"entity": "NoSuchEntity", "condition": "1 > 0"}],
    }
    resp = client.post("/api/v1/projects/import", json=template, headers=auth_headers)
    assert resp.status_code == 400

    after = len(client.get("/api/v1/projects", headers=auth_headers).json())
    assert after == before
