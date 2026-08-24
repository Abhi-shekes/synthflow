def test_signup_login_me_flow(client):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "a@example.com", "password": "hunter222222"}
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == "a@example.com"

    dup = client.post(
        "/api/v1/auth/signup", json={"email": "a@example.com", "password": "hunter222222"}
    )
    assert dup.status_code == 409

    bad_login = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong"}
    )
    assert bad_login.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "hunter222222"}
    )
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens
    # The refresh token never appears in the body — only as an httpOnly
    # cookie, scoped to the auth routes.
    assert "refresh_token" not in tokens
    assert "synthflow_refresh" in login.cookies

    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"
    # New accounts start guided and un-onboarded — the welcome flow and the
    # collapsed-by-default strata both depend on this default.
    assert me.json()["ui_mode"] == "guided"
    assert me.json()["has_onboarded"] is False

    # No body needed: the client's cookie jar carries the refresh cookie
    # `login` just set.
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()
    # Rotated: refreshing issues a new refresh cookie, and the one it was
    # called with is now dead.
    assert "synthflow_refresh" in refreshed.cookies

    logged_out = client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204

    reused_after_logout = client.post("/api/v1/auth/refresh")
    assert reused_after_logout.status_code == 401


def test_refresh_without_cookie_is_rejected(client):
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_login_locks_out_after_repeated_failures(client):
    email = "lockout@example.com"
    client.post("/api/v1/auth/signup", json={"email": email, "password": "hunter222222"})

    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert resp.status_code == 401

    locked = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter222222"})
    assert locked.status_code == 429


def test_signup_rejects_short_password(client):
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "short@example.com", "password": "short1"}
    )
    assert resp.status_code == 422


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_update_me_sets_mode_and_onboarding(client):
    email, password = "b@example.com", "hunter222222"
    client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.patch("/api/v1/auth/me", json={"ui_mode": "advanced"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ui_mode"] == "advanced"
    assert resp.json()["has_onboarded"] is False

    resp = client.patch("/api/v1/auth/me", json={"has_onboarded": True}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["has_onboarded"] is True
    # Untouched field survives an update that doesn't mention it.
    assert resp.json()["ui_mode"] == "advanced"


def test_update_me_requires_auth(client):
    resp = client.patch("/api/v1/auth/me", json={"ui_mode": "advanced"})
    assert resp.status_code == 401
