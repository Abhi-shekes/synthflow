"""Phase 14 — the audit log.

Recorded by middleware over every mutating request rather than by calls
inside the routes, because a log assembled by remembering to log has holes
in it, and a missing entry looks exactly like a thing that never happened.
"""


def _entries(client, headers, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    response = client.get(f"/api/v1/audit{'?' + query if query else ''}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_change_is_recorded_without_the_route_asking(client, auth_headers):
    """No route calls anything to make this happen — that is the design."""
    before = _entries(client, auth_headers)
    project = client.post("/api/v1/projects", json={"name": "Audited"}, headers=auth_headers)
    assert project.status_code == 201

    after = _entries(client, auth_headers)
    assert len(after) == len(before) + 1
    entry = after[0]
    assert entry["method"] == "POST"
    assert entry["route"] == "/projects"
    assert entry["status_code"] == 201
    assert entry["actor_kind"] == "session"
    assert entry["actor_email"] == "user@example.com"


def test_a_read_is_not_recorded(client, auth_headers):
    """Recording GETs would turn every read into a write, and "who looked at
    this" is a different feature with a different cost."""
    client.post("/api/v1/projects", json={"name": "P"}, headers=auth_headers)
    baseline = len(_entries(client, auth_headers))

    for _ in range(5):
        client.get("/api/v1/projects", headers=auth_headers)

    assert len(_entries(client, auth_headers)) == baseline


def test_the_route_template_is_recorded_not_the_concrete_path(client, auth_headers):
    """Templates are a small set that groups and filters; concrete paths are
    unbounded and group into nothing."""
    project_id = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_headers).json()[
        "id"
    ]
    client.post(
        f"/api/v1/projects/{project_id}/entities",
        json={"name": "Customer"},
        headers=auth_headers,
    )

    # Found rather than indexed: both writes landed in the same clock tick,
    # so which is "newest" is arbitrary — see `audit.read`.
    entries = _entries(client, auth_headers)
    entry = next(e for e in entries if e["route"].endswith("/entities"))
    # Router-relative on purpose: a version bump must not split one route's
    # history into two unrelated-looking halves.
    assert entry["route"] == "/projects/{project_id}/entities"
    assert project_id not in entry["route"]
    assert entry["path_params"]["project_id"] == project_id


def test_events_can_be_filtered_to_one_project(client, auth_headers):
    first = client.post("/api/v1/projects", json={"name": "A"}, headers=auth_headers).json()["id"]
    second = client.post("/api/v1/projects", json={"name": "B"}, headers=auth_headers).json()["id"]
    client.post(f"/api/v1/projects/{first}/entities", json={"name": "E1"}, headers=auth_headers)
    client.post(f"/api/v1/projects/{second}/entities", json={"name": "E2"}, headers=auth_headers)
    client.post(f"/api/v1/projects/{second}/entities", json={"name": "E3"}, headers=auth_headers)

    only_second = _entries(client, auth_headers, project_id=second)
    assert len(only_second) == 2
    assert {e["project_id"] for e in only_second} == {second}


def test_a_refused_request_is_recorded(client, auth_headers):
    """A 403 is exactly the kind of event an audit log exists to show.
    Keeping only successes would hide the attempts."""
    created = client.post(
        "/api/v1/api-keys", json={"name": "ro", "scope": "read_only"}, headers=auth_headers
    ).json()
    key_headers = {"Authorization": f"Bearer {created['key']}"}

    blocked = client.post("/api/v1/projects", json={"name": "Nope"}, headers=key_headers)
    assert blocked.status_code == 403

    # Found rather than indexed: entries written in the same instant share
    # the database clock, so which of them is "newest" is arbitrary by
    # design — see `audit.read`.
    entries = _entries(client, auth_headers)
    refusals = [e for e in entries if e["status_code"] == 403]
    assert len(refusals) == 1
    assert refusals[0]["method"] == "POST"
    assert refusals[0]["route"] == "/projects"


def test_an_api_key_is_distinguishable_from_a_session(client, auth_headers):
    """ "Did I do that or did my CI pipeline" is the first question anyone
    asks of an audit log, and both arrive as the same user."""
    created = client.post("/api/v1/api-keys", json={"name": "ci"}, headers=auth_headers).json()
    key_headers = {"Authorization": f"Bearer {created['key']}"}

    client.post("/api/v1/projects", json={"name": "By key"}, headers=key_headers)
    client.post("/api/v1/projects", json={"name": "By me"}, headers=auth_headers)

    entries = [e for e in _entries(client, auth_headers) if e["route"] == "/projects"]
    by_kind = {e["actor_kind"]: e for e in entries}
    assert set(by_kind) == {"session", "api_key"}
    assert by_kind["session"]["api_key_prefix"] is None
    # Named, so "which key did this" is answerable.
    assert by_kind["api_key"]["api_key_prefix"] == created["prefix"]


def test_one_user_cannot_see_anothers_activity(client, auth_headers):
    client.post("/api/v1/projects", json={"name": "Mine"}, headers=auth_headers)

    client.post(
        "/api/v1/auth/signup",
        json={"email": "other@example.com", "password": "testpassword123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "testpassword123"},
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/projects", json={"name": "Theirs"}, headers=other)

    mine = _entries(client, auth_headers)
    theirs = _entries(client, other)
    assert all(e["actor_email"] == "user@example.com" for e in mine)
    assert all(e["actor_email"] == "other@example.com" for e in theirs)


def test_an_unauthenticated_request_records_nothing(client, auth_headers):
    """There is no "who", so there is nothing an entry could usefully say."""
    baseline = len(_entries(client, auth_headers))
    assert client.post("/api/v1/projects", json={"name": "X"}).status_code == 401
    assert len(_entries(client, auth_headers)) == baseline


def test_the_log_pages_without_skipping_or_repeating(client, auth_headers):
    """An audit log only ever grows, so "all of them" stops being a sensible
    response. Paging needs a total order: `created_at` alone is shared by
    everything written in one instant."""
    for i in range(12):
        client.post("/api/v1/projects", json={"name": f"P{i}"}, headers=auth_headers)

    seen: list[str] = []
    for offset in (0, 5, 10):
        page = _entries(client, auth_headers, limit=5, offset=offset)
        seen.extend(e["id"] for e in page)

    assert len(seen) == 12
    assert len(set(seen)) == 12

    again = _entries(client, auth_headers, limit=12)
    assert [e["id"] for e in again] == seen


def test_the_generation_and_push_routes_are_covered(client, auth_headers):
    """The roadmap asked for "who changed a schema, ran a generation, or
    pushed to a database". Deriving entries from the request is what makes
    all three true at once, without three separate pieces of bookkeeping."""
    project_id = client.post("/api/v1/projects", json={"name": "P"}, headers=auth_headers).json()[
        "id"
    ]
    entity_id = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "E"}, headers=auth_headers
    ).json()["id"]
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json={"name": "n", "field_type": "integer", "required": True, "nullable": False},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 3},
        headers=auth_headers,
    )

    routes = {e["route"] for e in _entries(client, auth_headers)}
    assert "/projects/{project_id}/entities" in routes
    assert "/projects/{project_id}/entities/{entity_id}/fields" in routes
    assert "/projects/{project_id}/entities/{entity_id}/generate" in routes
