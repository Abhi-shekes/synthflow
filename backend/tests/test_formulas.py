def _create_project(client, headers):
    return client.post("/api/v1/projects", json={"name": "Retail"}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="LineItem"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_formula_field_computed_from_other_fields(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "price",
            "field_type": "float",
            "order": 0,
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 100,
        },
        headers=auth_headers,
    )
    client.post(
        f"{base}/fields",
        json={
            "name": "quantity",
            "field_type": "integer",
            "order": 1,
            "required": True,
            "nullable": False,
            "min_value": 1,
            "max_value": 10,
        },
        headers=auth_headers,
    )
    total_resp = client.post(
        f"{base}/fields",
        json={
            "name": "total",
            "field_type": "float",
            "order": 2,
            "required": True,
            "nullable": False,
            "formula": "price * quantity",
        },
        headers=auth_headers,
    )
    assert total_resp.status_code == 201

    resp = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert resp.status_code == 200
    for row in resp.json():
        assert row["total"] == row["price"] * row["quantity"]


def _pearson(xs, ys):
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    return cov / (var_x * var_y) ** 0.5


def test_correlated_field_via_formula_and_noise(client, auth_headers):
    # The "correlation engine" from the spec (temperature up -> humidity down)
    # is a formula field referencing an earlier field, with noise() for
    # realistic scatter instead of a perfectly deterministic line.
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id, "Weather")
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "temperature",
            "field_type": "integer",
            "order": 0,
            "required": True,
            "nullable": False,
            "min_value": 0,
            "max_value": 40,
        },
        headers=auth_headers,
    )
    humidity_resp = client.post(
        f"{base}/fields",
        json={
            "name": "humidity",
            "field_type": "float",
            "order": 1,
            "required": True,
            "nullable": False,
            "formula": "100 - temperature * 1.5 + noise(3)",
        },
        headers=auth_headers,
    )
    assert humidity_resp.status_code == 201

    resp = client.post(f"{base}/generate", json={"count": 100}, headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()

    temps = [row["temperature"] for row in rows]
    humidities = [row["humidity"] for row in rows]

    # Real noise, not a dead-flat deterministic line.
    assert len(set(humidities)) > 50

    # But still a strong negative correlation, as configured.
    r = _pearson(temps, humidities)
    assert r < -0.8


def test_formula_referencing_unknown_field_rejected_at_creation(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    resp = client.post(
        f"{base}/fields",
        json={
            "name": "total",
            "field_type": "float",
            "formula": "price * quantity",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
