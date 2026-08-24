def test_project_crud(client, auth_headers):
    create = client.post(
        "/api/v1/projects",
        json={"name": "Stock Market", "description": "NSE sim"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    listed = client.get("/api/v1/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Stock Market"

    updated = client.patch(
        f"/api/v1/projects/{project_id}", json={"name": "NSE Sim"}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "NSE Sim"

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert missing.status_code == 404


def test_projects_are_scoped_per_user(client):
    u1 = {"email": "u1@example.com", "password": "hunter222222"}
    client.post("/api/v1/auth/signup", json=u1)
    login1 = client.post("/api/v1/auth/login", json=u1)
    headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    u2 = {"email": "u2@example.com", "password": "hunter222222"}
    client.post("/api/v1/auth/signup", json=u2)
    login2 = client.post("/api/v1/auth/login", json=u2)
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    created = client.post("/api/v1/projects", json={"name": "Private"}, headers=headers1)
    project_id = created.json()["id"]

    stolen = client.get(f"/api/v1/projects/{project_id}", headers=headers2)
    assert stolen.status_code == 404
