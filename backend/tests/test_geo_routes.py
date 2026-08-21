def _create_project(client, headers, name="Fleet"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_position_field(client, headers, project_id, name="Vehicle"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "position", "field_type": "object", "required": True, "nullable": False},
        headers=headers,
    ).json()
    return entity["id"], field["id"]


def _upload_route(client, headers, project_id, csv_bytes, name="Route"):
    return client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": name},
        files={"file": ("route.csv", csv_bytes, "text/csv")},
        headers=headers,
    ).json()


TWO_WAYPOINTS = b"lat,lon,name\n10.0,20.0,start\n30.0,40.0,end\n"


def test_create_geo_route(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["lat_column"] == "lat"
    assert body["lon_column"] == "lon"


def test_field_must_be_object_or_json_type(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Vehicle"}, headers=auth_headers
    ).json()
    field = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "position", "field_type": "string", "required": True, "nullable": False},
        headers=auth_headers,
    ).json()
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/geo-routes",
        json={
            "field_id": field["id"],
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_lat_lon_columns_must_exist(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "nonexistent",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_lookup_table_must_belong_to_project(client, auth_headers):
    project_a = _create_project(client, auth_headers, "A")
    project_b = _create_project(client, auth_headers, "B")
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_b)
    route = _upload_route(client, auth_headers, project_a, TWO_WAYPOINTS)

    resp = client.post(
        f"/api/v1/projects/{project_b}/entities/{entity_id}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_lat_lon_values_must_be_numeric(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": "BadRoute"},
        files={
            "file": (
                "route.json",
                b'[{"lat": "10.0", "lon": "20.0"}]',
                "application/json",
            )
        },
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_only_one_geo_route_per_field(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)
    payload = {
        "field_id": field_id,
        "lookup_table_id": route["id"],
        "lat_column": "lat",
        "lon_column": "lon",
    }
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes"

    first = client.post(base, json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = client.post(base, json=payload, headers=auth_headers)
    assert second.status_code == 400


def test_delete_geo_route(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes"
    created = client.post(
        base,
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    ).json()

    deleted = client.delete(f"{base}/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(base, headers=auth_headers)
    assert listed.json() == []


def test_deleting_lookup_table_cascades_to_geo_route(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )

    client.delete(
        f"/api/v1/projects/{project_id}/lookup-tables/{route['id']}", headers=auth_headers
    )

    listed = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/geo-routes", headers=auth_headers
    )
    assert listed.json() == []


def test_geo_route_generates_interpolated_points_along_the_path(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    route = _upload_route(client, auth_headers, project_id, TWO_WAYPOINTS)
    client.post(
        f"{base}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 11}, headers=auth_headers)
    assert gen.status_code == 200
    rows = gen.json()
    positions = [row["position"] for row in rows]

    # 11 rows over a lat 10->30, lon 20->40 path should land on exact 2-unit
    # (lat) / 4-unit (lon) steps: row i is at progress i/10.
    assert positions[0] == {"lat": 10.0, "lon": 20.0}
    assert positions[-1] == {"lat": 30.0, "lon": 40.0}
    assert positions[5] == {"lat": 20.0, "lon": 30.0}
    lats = [p["lat"] for p in positions]
    assert lats == sorted(lats)


def test_single_waypoint_route_returns_constant_point(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id, field_id = _create_entity_with_position_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    route = _upload_route(client, auth_headers, project_id, b"lat,lon\n5.0,6.0\n")
    client.post(
        f"{base}/geo-routes",
        json={
            "field_id": field_id,
            "lookup_table_id": route["id"],
            "lat_column": "lat",
            "lon_column": "lon",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    positions = [row["position"] for row in gen.json()]
    assert all(p == {"lat": 5.0, "lon": 6.0} for p in positions)
