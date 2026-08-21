import base64

from app.models.field import IdentifierPreset


def _create_project(client, headers, name="Identifiers"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity(client, headers, project_id, name="Record"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def test_pan_preset_matches_the_real_pan_shape(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    field = client.post(
        f"{base}/fields",
        json={
            "name": "pan",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "pan",
        },
        headers=auth_headers,
    )
    assert field.status_code == 201
    assert field.json()["preset"] == "pan"

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["pan"]
        assert len(value) == 10
        assert value[:5].isalpha() and value[:5].isupper()
        assert value[5:9].isdigit()
        assert value[9].isalpha() and value[9].isupper()


def test_vin_preset_excludes_i_o_q(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "vin",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "vin",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["vin"]
        assert len(value) == 17
        assert not any(c in value for c in "IOQ")


def test_imei_preset_has_a_valid_luhn_check_digit(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "imei",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "imei",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 15}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["imei"]
        assert len(value) == 15 and value.isdigit()
        total = 0
        for i, ch in enumerate(reversed(value)):
            digit = int(ch)
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        assert total % 10 == 0


def test_gstin_preset_matches_the_real_gstin_shape(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "gstin",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "gstin",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["gstin"]
        assert len(value) == 15
        assert value[:2].isdigit()
        assert value[13] == "Z"


def test_qr_code_preset_produces_a_valid_png_data_uri(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "code",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "qr_code",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["code"]
        assert value.startswith("data:image/png;base64,")
        png_bytes = base64.b64decode(value.removeprefix("data:image/png;base64,"))
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_business_email_preset_looks_like_an_email(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "email",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "preset": "business_email",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 10}, headers=auth_headers)
    assert gen.status_code == 200
    for row in gen.json():
        value = row["email"]
        assert "@" in value
        local, _, domain = value.partition("@")
        assert "." in local
        assert "." in domain


def test_every_identifier_preset_generates_a_non_empty_value(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    for preset in IdentifierPreset:
        entity_id = _create_entity(client, auth_headers, project_id, name=f"Entity-{preset}")
        base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
        client.post(
            f"{base}/fields",
            json={
                "name": "value",
                "field_type": "string",
                "required": True,
                "nullable": False,
                "preset": preset.value,
            },
            headers=auth_headers,
        )
        gen = client.post(f"{base}/generate", json={"count": 3}, headers=auth_headers)
        assert gen.status_code == 200, preset
        values = [row["value"] for row in gen.json()]
        assert all(isinstance(v, str) and v for v in values), preset


def test_unique_field_with_identifier_preset_generates_distinct_values(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"

    client.post(
        f"{base}/fields",
        json={
            "name": "vin",
            "field_type": "string",
            "required": True,
            "nullable": False,
            "unique": True,
            "preset": "vin",
        },
        headers=auth_headers,
    )

    gen = client.post(f"{base}/generate", json={"count": 20}, headers=auth_headers)
    assert gen.status_code == 200
    values = [row["vin"] for row in gen.json()]
    assert len(set(values)) == 20
