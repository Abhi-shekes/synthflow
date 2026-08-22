"""Phase 14 — organisations, roles and shared projects.

Before this, "may I touch this project" was `project.owner_id == user.id`,
written out behind two helpers that 118 route call sites go through. Those
two helpers are the extension point: the rule moved, the call sites did not.
"""

import pytest


def _signup(client, email):
    client.post("/api/v1/auth/signup", json={"email": email, "password": "testpassword123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "testpassword123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def owner(auth_headers):
    return auth_headers


@pytest.fixture()
def teammate(client):
    return _signup(client, "teammate@example.com")


@pytest.fixture()
def outsider(client):
    return _signup(client, "outsider@example.com")


def _org(client, headers, name="Acme"):
    response = client.post("/api/v1/organizations", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add(client, headers, org_id, email, role="member"):
    return client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"email": email, "role": role},
        headers=headers,
    )


def _project(client, headers, name="Shared"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _share(client, headers, project_id, org_id):
    return client.put(
        f"/api/v1/projects/{project_id}/organization",
        json={"organization_id": org_id},
        headers=headers,
    )


# --------------------------------------------------------------------------
# Nothing changes for a single user
# --------------------------------------------------------------------------


def test_a_personal_project_behaves_exactly_as_before(client, owner, outsider):
    """Every existing project keeps `organization_id` null, so this is the
    whole compatibility story."""
    project_id = _project(client, owner)

    assert client.get(f"/api/v1/projects/{project_id}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}", headers=outsider).status_code == 404
    assert client.get("/api/v1/projects", headers=outsider).json() == []


# --------------------------------------------------------------------------
# Sharing
# --------------------------------------------------------------------------


def test_a_shared_project_becomes_visible_to_the_organisation(client, owner, teammate, outsider):
    org_id = _org(client, owner)
    assert _add(client, owner, org_id, "teammate@example.com").status_code == 201
    project_id = _project(client, owner)

    # Not shared yet.
    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 404

    assert _share(client, owner, project_id, org_id).status_code == 200

    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 200
    assert [p["id"] for p in client.get("/api/v1/projects", headers=teammate).json()] == [
        project_id
    ]
    # And still invisible to someone outside the organisation.
    assert client.get(f"/api/v1/projects/{project_id}", headers=outsider).status_code == 404


def test_unsharing_takes_it_back(client, owner, teammate):
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)
    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 200

    client.put(
        f"/api/v1/projects/{project_id}/organization",
        json={"organization_id": None},
        headers=owner,
    )
    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 404


def test_only_the_projects_owner_can_share_it(client, owner, teammate):
    """An admin who could move projects in and out of their organisation
    could quietly take one over."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="admin")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)

    other_org = _org(client, teammate, name="Theirs")
    stolen = client.put(
        f"/api/v1/projects/{project_id}/organization",
        json={"organization_id": other_org},
        headers=teammate,
    )
    assert stolen.status_code == 403
    assert "owner" in stolen.json()["detail"]


def test_a_project_cannot_be_shared_into_an_organisation_you_are_not_in(client, owner, teammate):
    theirs = _org(client, teammate, name="Theirs")
    project_id = _project(client, owner)

    response = _share(client, owner, project_id, theirs)
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


def test_a_viewer_may_read_but_not_write(client, owner, teammate):
    """Enforced by HTTP method, not a per-route list — the same rule the
    read-only API key uses, so the two cannot drift apart."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="viewer")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)

    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 200
    assert (
        client.get(f"/api/v1/projects/{project_id}/entities", headers=teammate).status_code == 200
    )

    blocked = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "E"}, headers=teammate
    )
    assert blocked.status_code == 403
    assert "viewer" in blocked.json()["detail"]


def test_a_member_may_write(client, owner, teammate):
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="member")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)

    created = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "E"}, headers=teammate
    )
    assert created.status_code == 201


def test_the_owner_keeps_full_access_whatever_the_organisation_says(client, owner, teammate):
    """Moving a project into an organisation must not be a way to lock its
    owner out of it."""
    org_id = _org(client, teammate, name="Theirs")
    _add(client, teammate, org_id, "user@example.com", role="viewer")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)

    # Owner is a viewer of the org, yet still writes their own project.
    created = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "E"}, headers=owner
    )
    assert created.status_code == 201


def test_nested_resources_inherit_the_rule(client, owner, teammate):
    """`_get_owned_entity` delegates to `_get_owned_project`, which is why
    118 call sites needed no change."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="viewer")
    project_id = _project(client, owner)
    entity_id = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "E"}, headers=owner
    ).json()["id"]
    _share(client, owner, project_id, org_id)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    assert client.get(base, headers=teammate).status_code == 200
    blocked = client.post(
        f"{base}/fields",
        json={"name": "n", "field_type": "integer", "required": True, "nullable": False},
        headers=teammate,
    )
    assert blocked.status_code == 403


# --------------------------------------------------------------------------
# Membership management
# --------------------------------------------------------------------------


def test_the_creator_becomes_the_owner(client, owner):
    org_id = _org(client, owner)
    listed = client.get("/api/v1/organizations", headers=owner).json()
    assert listed[0]["my_role"] == "owner"

    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=owner).json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


def test_a_member_cannot_manage_membership(client, owner, teammate):
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="member")

    refused = _add(client, teammate, org_id, "outsider@example.com")
    assert refused.status_code == 403


def test_an_admin_cannot_grant_a_role_above_their_own(client, owner, teammate, outsider):
    """An admin who could mint an owner could promote themselves through a
    second account, which makes the ladder decorative."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="admin")

    refused = _add(client, teammate, org_id, "outsider@example.com", role="owner")
    assert refused.status_code == 403
    assert "above your own role" in refused.json()["detail"]

    allowed = _add(client, teammate, org_id, "outsider@example.com", role="member")
    assert allowed.status_code == 201


def test_an_admin_cannot_remove_an_owner(client, owner, teammate):
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="admin")
    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=owner).json()
    owner_member = next(m for m in members if m["role"] == "owner")

    refused = client.delete(
        f"/api/v1/organizations/{org_id}/members/{owner_member['id']}", headers=teammate
    )
    assert refused.status_code == 403


def test_the_last_owner_cannot_be_removed_or_demoted(client, owner, teammate):
    """Otherwise the organisation is left with nobody who can administer it,
    delete it, or add anyone back."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="admin")
    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=owner).json()
    me = next(m for m in members if m["role"] == "owner")

    demoted = client.patch(
        f"/api/v1/organizations/{org_id}/members/{me['id']}",
        json={"role": "member"},
        headers=owner,
    )
    assert demoted.status_code == 400
    assert "last owner" in demoted.json()["detail"]

    removed = client.delete(f"/api/v1/organizations/{org_id}/members/{me['id']}", headers=owner)
    assert removed.status_code == 400

    # With a second owner it is allowed.
    teammate_member = next(m for m in members if m["role"] == "admin")
    client.patch(
        f"/api/v1/organizations/{org_id}/members/{teammate_member['id']}",
        json={"role": "owner"},
        headers=owner,
    )
    assert (
        client.delete(
            f"/api/v1/organizations/{org_id}/members/{me['id']}", headers=owner
        ).status_code
        == 204
    )


def test_adding_an_unknown_email_says_so(client, owner):
    org_id = _org(client, owner)
    response = _add(client, owner, org_id, "nobody@example.com")
    assert response.status_code == 404
    assert "sign up" in response.json()["detail"]


def test_an_organisation_you_are_not_in_is_a_404(client, owner, outsider):
    org_id = _org(client, owner)
    assert (
        client.get(f"/api/v1/organizations/{org_id}/members", headers=outsider).status_code == 404
    )
    assert client.get("/api/v1/organizations", headers=outsider).json() == []


def test_dissolving_an_organisation_returns_its_projects_rather_than_deleting_them(
    client, owner, teammate
):
    """Destroying other people's work as a side effect of tidying up a group
    would be a spectacular way to lose data."""
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com")
    project_id = _project(client, owner)
    _share(client, owner, project_id, org_id)

    assert client.delete(f"/api/v1/organizations/{org_id}", headers=owner).status_code == 204

    still_there = client.get(f"/api/v1/projects/{project_id}", headers=owner)
    assert still_there.status_code == 200
    assert still_there.json()["organization_id"] is None
    # And it is personal again, so the teammate loses access.
    assert client.get(f"/api/v1/projects/{project_id}", headers=teammate).status_code == 404


def test_only_an_owner_can_dissolve_an_organisation(client, owner, teammate):
    org_id = _org(client, owner)
    _add(client, owner, org_id, "teammate@example.com", role="admin")
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=teammate).status_code == 403
