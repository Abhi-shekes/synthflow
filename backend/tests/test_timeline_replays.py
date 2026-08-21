def _create_project(client, headers, name="Historical"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _upload_lookup_table(client, headers, project_id, rows_csv, name="Events"):
    return client.post(
        f"/api/v1/projects/{project_id}/lookup-tables",
        data={"name": name},
        files={"file": ("events.csv", rows_csv, "text/csv")},
        headers=headers,
    ).json()


def test_create_timeline_replay(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client,
        auth_headers,
        project_id,
        b"ts,event\n2024-01-01T00:00:00,login\n2024-01-01T00:00:01,click\n",
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={
            "lookup_table_id": lookup_table["id"],
            "timestamp_column": "ts",
            "speed_multiplier": 60,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["timestamp_column"] == "ts"
    assert body["speed_multiplier"] == 60
    assert "token" in body


def test_lookup_table_must_belong_to_project(client, auth_headers):
    project_a = _create_project(client, auth_headers, "A")
    project_b = _create_project(client, auth_headers, "B")
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_a, b"ts,event\n2024-01-01T00:00:00,login\n"
    )

    resp = client.post(
        f"/api/v1/projects/{project_b}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "ts"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_timestamp_column_must_exist(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_id, b"ts,event\n2024-01-01T00:00:00,login\n"
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "nonexistent"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_timestamp_column_values_must_be_iso8601(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_id, b"ts,event\nnot-a-timestamp,login\n"
    )

    resp = client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "ts"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_list_and_delete_timeline_replay(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_id, b"ts,event\n2024-01-01T00:00:00,login\n"
    )
    created = client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "ts"},
        headers=auth_headers,
    ).json()

    listed = client.get(f"/api/v1/projects/{project_id}/timeline-replays", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(
        f"/api/v1/projects/{project_id}/timeline-replays/{created['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204

    listed_after = client.get(
        f"/api/v1/projects/{project_id}/timeline-replays", headers=auth_headers
    )
    assert listed_after.json() == []


def test_deleting_lookup_table_cascades_to_replay(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_id, b"ts,event\n2024-01-01T00:00:00,login\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "ts"},
        headers=auth_headers,
    )

    client.delete(
        f"/api/v1/projects/{project_id}/lookup-tables/{lookup_table['id']}", headers=auth_headers
    )

    listed = client.get(f"/api/v1/projects/{project_id}/timeline-replays", headers=auth_headers)
    assert listed.json() == []


def test_replay_rejects_unknown_token(client):
    with client.websocket_connect("/public/replay/does-not-exist") as ws:
        message = ws.receive_json()
        assert "error" in message


def test_replay_sends_rows_in_timestamp_order_and_loops(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    # Uploaded out of timestamp order on purpose, to prove sort-by-column
    # rather than upload-order drives playback.
    lookup_table = _upload_lookup_table(
        client,
        auth_headers,
        project_id,
        b"ts,event\n"
        b"2024-01-01T00:00:02,third\n"
        b"2024-01-01T00:00:00,first\n"
        b"2024-01-01T00:00:01,second\n",
    )
    created = client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        # speed_multiplier high enough that real 1s/2s gaps become
        # near-instant, keeping the test fast without changing the ordering
        # or wraparound logic under test.
        json={
            "lookup_table_id": lookup_table["id"],
            "timestamp_column": "ts",
            "speed_multiplier": 1000,
        },
        headers=auth_headers,
    ).json()

    with client.websocket_connect(f"/public/replay/{created['token']}") as ws:
        messages = [ws.receive_json() for _ in range(4)]

    assert [m["event"] for m in messages] == ["first", "second", "third", "first"]


def test_replay_appears_in_outputs_aggregate(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    lookup_table = _upload_lookup_table(
        client, auth_headers, project_id, b"ts,event\n2024-01-01T00:00:00,login\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/timeline-replays",
        json={"lookup_table_id": lookup_table["id"], "timestamp_column": "ts"},
        headers=auth_headers,
    )

    resp = client.get(f"/api/v1/projects/{project_id}/outputs", headers=auth_headers)
    assert resp.status_code == 200
    assert any(o["type"] == "timeline_replay" for o in resp.json())
