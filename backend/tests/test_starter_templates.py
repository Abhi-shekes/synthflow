import pytest

from app.services.starter_templates import list_starter_templates, load_starter_template

EXPECTED_KEYS = {
    "banking",
    "stock_market",
    "smart_city",
    "weather",
    "hospital",
    "manufacturing",
    "cctv",
    "logistics",
    "gps_fleet",
    "retail",
    "iot",
}


def test_bundled_starter_templates_cover_every_roadmap_domain():
    summaries = list_starter_templates()
    assert {s.key for s in summaries} == EXPECTED_KEYS
    for summary in summaries:
        assert summary.name
        assert summary.description


def test_load_starter_template_returns_a_valid_project_template():
    template = load_starter_template("banking")
    assert template.name == "Banking"
    assert len(template.entities) > 0


def test_load_unknown_starter_template_raises():
    with pytest.raises(ValueError):
        load_starter_template("not_a_real_template")


def test_list_starter_templates_route(client, auth_headers):
    resp = client.get("/api/v1/starter-templates", headers=auth_headers)
    assert resp.status_code == 200
    keys = {t["key"] for t in resp.json()}
    assert keys == EXPECTED_KEYS


def test_list_starter_templates_route_requires_auth(client):
    resp = client.get("/api/v1/starter-templates")
    assert resp.status_code == 401


def test_get_starter_template_route(client, auth_headers):
    resp = client.get("/api/v1/starter-templates/retail", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Retail"
    assert len(body["entities"]) > 0


def test_get_unknown_starter_template_route_404s(client, auth_headers):
    resp = client.get("/api/v1/starter-templates/not_a_real_template", headers=auth_headers)
    assert resp.status_code == 404


def test_every_starter_template_imports_and_generates_working_rows(client, auth_headers):
    """The real proof: every bundled template goes through the exact same
    /projects/import path a hand-exported project would, then a
    project-wide /generate call must return the right shape for every
    entity and field the template declares — not just that the JSON
    validates against the schema."""
    for summary in list_starter_templates():
        template = load_starter_template(summary.key)

        imported = client.post(
            "/api/v1/projects/import", json=template.model_dump(), headers=auth_headers
        )
        assert imported.status_code == 201, f"{summary.key}: {imported.text}"
        project = imported.json()

        gen = client.post(
            f"/api/v1/projects/{project['id']}/generate",
            json={"count": 5, "counts": {}},
            headers=auth_headers,
        )
        assert gen.status_code == 200, f"{summary.key}: {gen.text}"
        body = gen.json()

        for entity_template in template.entities:
            rows = body[entity_template.name]
            assert len(rows) == 5, f"{summary.key}.{entity_template.name}"
            for row in rows:
                for field_template in entity_template.fields:
                    assert field_template.name in row, (
                        f"{summary.key}.{entity_template.name}.{field_template.name}"
                    )
