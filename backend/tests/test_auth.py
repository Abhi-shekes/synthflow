def test_signup_login_me_flow(client):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "a@example.com", "password": "hunter22"}
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == "a@example.com"

    dup = client.post(
        "/api/v1/auth/signup", json={"email": "a@example.com", "password": "hunter22"}
    )
    assert dup.status_code == 409

    bad_login = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong"}
    )
    assert bad_login.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "hunter22"}
    )
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
