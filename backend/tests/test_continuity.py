"""Phase 13 — persistent record identity and cross-call continuity.

The behaviour under test is what every previous phase deliberately did not
do: a second generation call that knows about the first.
"""


def _project(client, headers, name="Continuity"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _entity(client, headers, project_id, name):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def _field(client, headers, project_id, entity_id, name, field_type="uuid", **extra):
    payload = {
        "name": name,
        "field_type": field_type,
        "required": True,
        "nullable": False,
        **extra,
    }
    return client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json=payload,
        headers=headers,
    ).json()["id"]


def _store(client, headers, project_id, entity_id, identity_field_id, name="default"):
    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": name, "identity_field_id": identity_field_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _generate(client, headers, project_id, entity_id, store_id, count):
    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/generate",
        json={"count": count},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Persistent identity
# --------------------------------------------------------------------------


def test_records_generated_yesterday_are_still_there_today(client, auth_headers):
    """The whole point of the phase: two calls accumulate one population
    rather than producing two unrelated ones."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    first = _generate(client, auth_headers, project_id, entity_id, store_id, 5)
    second = _generate(client, auth_headers, project_id, entity_id, store_id, 3)

    assert first["total_active"] == 5
    assert second["total_active"] == 8

    records = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/records",
        headers=auth_headers,
    ).json()
    assert len(records) == 8
    # Every identity distinct, and every one of the first call's records
    # still present after the second.
    identities = {r["identity"] for r in records}
    assert len(identities) == 8
    assert {str(row["customer_id"]) for row in first["rows"]} <= identities


def test_a_child_draws_foreign_keys_from_the_parents_stored_population(client, auth_headers):
    """ "...and can receive new orders." The orders are generated in a
    separate call from the customers, so a batch-local pool cannot be what
    they are drawing from."""
    project_id = _project(client, auth_headers)
    customer_id = _entity(client, auth_headers, project_id, "Customer")
    customer_key = _field(client, auth_headers, project_id, customer_id, "customer_id")
    customer_store = _store(client, auth_headers, project_id, customer_id, customer_key)

    order_id = _entity(client, auth_headers, project_id, "Order")
    order_key = _field(client, auth_headers, project_id, order_id, "order_id")
    order_fk = _field(client, auth_headers, project_id, order_id, "customer_id")
    order_store = _store(client, auth_headers, project_id, order_id, order_key)

    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order_id,
            "source_field_id": order_fk,
            "target_entity_id": customer_id,
            "target_field_id": customer_key,
        },
        headers=auth_headers,
    )

    customers = _generate(client, auth_headers, project_id, customer_id, customer_store, 4)
    customer_keys = {str(row["customer_id"]) for row in customers["rows"]}

    orders = _generate(client, auth_headers, project_id, order_id, order_store, 12)
    referenced = {str(row["customer_id"]) for row in orders["rows"]}

    assert referenced <= customer_keys
    # Not vacuous: with 12 orders over 4 customers, more than one customer
    # should actually be used.
    assert len(referenced) > 1


def test_a_child_generated_later_still_reaches_the_earlier_customers(client, auth_headers):
    """A second batch of orders draws from customers stored in a call that
    finished long before it — including customers the first order batch
    never touched."""
    project_id = _project(client, auth_headers)
    customer_id = _entity(client, auth_headers, project_id, "Customer")
    customer_key = _field(client, auth_headers, project_id, customer_id, "customer_id")
    customer_store = _store(client, auth_headers, project_id, customer_id, customer_key)

    order_id = _entity(client, auth_headers, project_id, "Order")
    order_key = _field(client, auth_headers, project_id, order_id, "order_id")
    order_fk = _field(client, auth_headers, project_id, order_id, "customer_id")
    order_store = _store(client, auth_headers, project_id, order_id, order_key)

    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order_id,
            "source_field_id": order_fk,
            "target_entity_id": customer_id,
            "target_field_id": customer_key,
        },
        headers=auth_headers,
    )

    first_customers = _generate(client, auth_headers, project_id, customer_id, customer_store, 3)
    early_keys = {str(row["customer_id"]) for row in first_customers["rows"]}
    _generate(client, auth_headers, project_id, order_id, order_store, 5)

    # A later customer batch, then later orders. The orders must be able to
    # reach both generations of customers.
    _generate(client, auth_headers, project_id, customer_id, customer_store, 3)
    later_orders = _generate(client, auth_headers, project_id, order_id, order_store, 40)

    referenced = {str(row["customer_id"]) for row in later_orders["rows"]}
    assert referenced & early_keys, "later orders never reached the first batch of customers"


def test_two_stores_on_one_entity_keep_separate_populations(client, auth_headers):
    """Two consumers of the same schema are not watching the same
    population — a demo stream must not consume a nightly feed's state."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    demo = _store(client, auth_headers, project_id, entity_id, identity, name="demo")
    nightly = _store(client, auth_headers, project_id, entity_id, identity, name="nightly")

    _generate(client, auth_headers, project_id, entity_id, demo, 5)
    nightly_result = _generate(client, auth_headers, project_id, entity_id, nightly, 2)

    assert nightly_result["total_active"] == 2
    assert nightly_result["position"] == 2


# --------------------------------------------------------------------------
# Cross-call continuity of position-based features
# --------------------------------------------------------------------------


def test_a_linear_trend_continues_instead_of_replaying_from_its_start(client, auth_headers):
    """The documented Phase 4 reset, closed. Without a cursor the second
    batch would repeat the first batch's values exactly."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Reading")
    identity = _field(client, auth_headers, project_id, entity_id, "reading_id")
    value_field = _field(client, auth_headers, project_id, entity_id, "value", field_type="float")
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/trends",
        json={
            "field_id": value_field,
            "trend_type": "linear",
            "params": {"start": 10, "slope": 2},
        },
        headers=auth_headers,
    )
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    first = _generate(client, auth_headers, project_id, entity_id, store_id, 5)
    second = _generate(client, auth_headers, project_id, entity_id, store_id, 5)

    assert [row["value"] for row in first["rows"]] == [10 + 2 * i for i in range(5)]
    # Continues at position 5, rather than starting over at 10.
    assert [row["value"] for row in second["rows"]] == [10 + 2 * i for i in range(5, 10)]
    assert second["position"] == 10


def test_a_random_walk_carries_its_running_value_across_calls(client, auth_headers):
    """`random_walk` keeps state in a dict the engine used to rebuild every
    call, snapping the series back to `start`. The store persists it, so the
    second batch begins within one step of where the first ended."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Reading")
    identity = _field(client, auth_headers, project_id, entity_id, "reading_id")
    value_field = _field(client, auth_headers, project_id, entity_id, "value", field_type="float")
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/trends",
        json={
            "field_id": value_field,
            "trend_type": "random_walk",
            "params": {"start": 100, "step_size": 1},
        },
        headers=auth_headers,
    )
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    first = _generate(client, auth_headers, project_id, entity_id, store_id, 30)
    second = _generate(client, auth_headers, project_id, entity_id, store_id, 30)

    last_of_first = first["rows"][-1]["value"]
    first_of_second = second["rows"][0]["value"]
    # One step of at most step_size. Without persistence this would jump
    # back to 100, which 30 steps of size 1 will have wandered away from.
    assert abs(first_of_second - last_of_first) <= 1.01


def test_records_come_back_in_the_order_they_were_created(client, auth_headers):
    """`created_at` cannot order them: every record from one call shares a
    transaction timestamp, so a batch came back shuffled by whatever the
    tiebreaker was. A linear trend makes the real order visible — the
    values must climb monotonically across both calls."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Reading")
    identity = _field(client, auth_headers, project_id, entity_id, "reading_id")
    value_field = _field(client, auth_headers, project_id, entity_id, "value", field_type="float")
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/trends",
        json={
            "field_id": value_field,
            "trend_type": "linear",
            "params": {"start": 100, "slope": 5},
        },
        headers=auth_headers,
    )
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 10)
    _generate(client, auth_headers, project_id, entity_id, store_id, 10)

    records = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/records",
        headers=auth_headers,
    ).json()

    assert [r["sequence"] for r in records] == list(range(20))
    assert [r["data"]["value"] for r in records] == [100 + 5 * i for i in range(20)]


def test_paging_over_a_store_neither_skips_nor_repeats(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    _generate(client, auth_headers, project_id, entity_id, store_id, 25)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/records"
    seen: list[str] = []
    for offset in (0, 10, 20):
        page = client.get(f"{base}?limit=10&offset={offset}", headers=auth_headers).json()
        seen.extend(r["identity"] for r in page)

    assert len(seen) == 25
    assert len(set(seen)) == 25


def test_the_cursor_survives_a_store_being_read_back(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Reading")
    identity = _field(client, auth_headers, project_id, entity_id, "reading_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 7)
    read_back = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}",
        headers=auth_headers,
    ).json()

    assert read_back["position"] == 7
    assert read_back["active_records"] == 7
    assert read_back["deleted_records"] == 0


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


def test_a_nullable_field_cannot_identify_records(client, auth_headers):
    """Refused at store creation rather than partway through a generation
    call that has already stored some records."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    field_id = _field(
        client,
        auth_headers,
        project_id,
        entity_id,
        "maybe_id",
        required=False,
        nullable=True,
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": "default", "identity_field_id": field_id},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "nullable" in response.json()["detail"].lower()


def test_an_identity_field_from_another_entity_is_refused(client, auth_headers):
    project_id = _project(client, auth_headers)
    first = _entity(client, auth_headers, project_id, "Customer")
    second = _entity(client, auth_headers, project_id, "Order")
    other_field = _field(client, auth_headers, project_id, second, "order_id")

    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{first}/record-stores",
        json={"name": "default", "identity_field_id": other_field},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_two_stores_cannot_share_a_name_on_one_entity(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _store(client, auth_headers, project_id, entity_id, identity, name="nightly")

    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": "nightly", "identity_field_id": identity},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_an_exhausted_identity_space_fails_loudly(client, auth_headers):
    """An enum identity with three values cannot supply a fourth distinct
    record. Better a clear error than a silent short batch or an infinite
    retry loop."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Region")
    identity = _field(
        client,
        auth_headers,
        project_id,
        entity_id,
        "region",
        field_type="enum",
        enum_values=["north", "south", "east"],
    )
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/generate",
        json={"count": 10},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "distinct values" in response.json()["detail"]

    # And the failed call left nothing behind — a partially-filled store
    # would be worse than none, since the caller cannot tell how far it got.
    stats = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}",
        headers=auth_headers,
    ).json()
    assert stats["active_records"] == 0
    assert stats["position"] == 0


def test_a_store_on_another_users_project_is_not_reachable(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    client.post(
        "/api/v1/auth/signup",
        json={"email": "intruder@example.com", "password": "testpassword123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "testpassword123"},
    ).json()["access_token"]
    intruder = {"Authorization": f"Bearer {token}"}

    response = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}",
        headers=intruder,
    )
    assert response.status_code == 404


def test_deleting_a_store_takes_its_records_with_it(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    _generate(client, auth_headers, project_id, entity_id, store_id, 3)

    deleted = client.delete(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    listed = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        headers=auth_headers,
    ).json()
    assert listed == []


# --------------------------------------------------------------------------
# Change data capture
# --------------------------------------------------------------------------


def _changes(client, headers, project_id, entity_id, store_id, **counts):
    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/changes",
        json=counts,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_tick_produces_inserts_updates_and_deletes_in_order(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 10)
    tick = _changes(
        client, auth_headers, project_id, entity_id, store_id, inserts=2, updates=3, deletes=1
    )

    operations = [e["operation"] for e in tick["events"]]
    # Inserts are logged by the generate step and are not in this call's
    # returned events; updates and deletes are, in that order.
    assert operations == ["update"] * 3 + ["delete"]
    assert tick["total_active"] == 11  # 10 + 2 inserted - 1 deleted

    log = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/changes"
        "?limit=1000",
        headers=auth_headers,
    ).json()
    assert [e["sequence"] for e in log] == list(range(len(log)))
    assert [e["operation"] for e in log[:10]] == ["insert"] * 10


def test_an_update_carries_the_row_before_and_after(client, auth_headers):
    """A consumer must be able to tell which columns actually moved without
    diffing against state it may not hold — the shape Debezium produces."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 5)
    tick = _changes(client, auth_headers, project_id, entity_id, store_id, updates=5)

    for event in tick["events"]:
        assert event["before"] is not None
        assert event["after"] is not None
        # The identity never moves — an update that changed it would be a
        # delete and an unrelated insert wearing one event's clothing.
        assert event["before"]["customer_id"] == event["after"]["customer_id"]
        assert str(event["after"]["customer_id"]) == event["identity"]
        assert event["version"] == 2


def test_a_delete_carries_the_row_it_removed_and_leaves_a_tombstone(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 4)
    tick = _changes(client, auth_headers, project_id, entity_id, store_id, deletes=2)

    for event in tick["events"]:
        assert event["operation"] == "delete"
        assert event["before"] is not None
        assert event["after"] is None

    stats = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}",
        headers=auth_headers,
    ).json()
    # The rows are still there as tombstones, not gone. A row that has been
    # removed cannot tell a consumer it was removed.
    assert stats["active_records"] == 2
    assert stats["deleted_records"] == 2


def test_a_deleted_record_never_receives_another_change(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 6)
    first = _changes(client, auth_headers, project_id, entity_id, store_id, deletes=3)
    gone = {e["identity"] for e in first["events"]}

    # Churn hard enough that a live-population bug would show.
    for _ in range(3):
        tick = _changes(client, auth_headers, project_id, entity_id, store_id, updates=3)
        assert {e["identity"] for e in tick["events"]}.isdisjoint(gone)


def test_one_record_is_not_changed_twice_in_a_single_tick(client, auth_headers):
    """Two events for one record at the same instant would reach a consumer
    with no way to order them."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 10)
    tick = _changes(client, auth_headers, project_id, entity_id, store_id, updates=5, deletes=5)

    touched = [e["identity"] for e in tick["events"]]
    assert len(touched) == len(set(touched)) == 10


def test_a_consumer_resumes_from_its_cursor_without_gaps_or_repeats(client, auth_headers):
    """The Kafka-offset contract: pass back the last sequence handled."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 5)
    _changes(client, auth_headers, project_id, entity_id, store_id, inserts=2, updates=2)
    _changes(client, auth_headers, project_id, entity_id, store_id, updates=1, deletes=1)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/changes"
    cursor = -1
    seen: list[int] = []
    while True:
        page = client.get(f"{base}?after={cursor}&limit=3", headers=auth_headers).json()
        if not page:
            break
        seen.extend(e["sequence"] for e in page)
        cursor = page[-1]["sequence"]

    assert seen == list(range(len(seen)))
    assert len(seen) == 5 + 2 + 2 + 1 + 1


def test_a_workflow_field_advances_rather_than_restarting(client, auth_headers):
    """The second documented Phase 4 reset, closed. A record that reached
    'checkout' must not be sent back to 'signed_up' by an update."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    stage = _field(client, auth_headers, project_id, entity_id, "stage", field_type="string")
    states = ["signed_up", "browsing", "cart", "checkout", "purchased"]
    created = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/workflows",
        json={
            "field_id": stage,
            "states": states,
            "initial_states": ["signed_up"],
            "transitions": [
                {"source": a, "target": b} for a, b in zip(states, states[1:], strict=False)
            ],
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 20)

    order = {name: i for i, name in enumerate(states)}
    # Every update must move a record forward along the chain or leave it
    # where it is — never backwards.
    for _ in range(6):
        tick = _changes(client, auth_headers, project_id, entity_id, store_id, updates=20)
        for event in tick["events"]:
            assert order[event["after"]["stage"]] >= order[event["before"]["stage"]]

    records = client.get(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/records"
        "?limit=100",
        headers=auth_headers,
    ).json()
    reached = {r["data"]["stage"] for r in records}
    # After six ticks on a five-state chain, the population should have
    # spread past its initial state. A restarting walk could not do this.
    assert reached != {"signed_up"}


def test_only_the_named_fields_change(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    _field(client, auth_headers, project_id, entity_id, "plan", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 8)
    tick = _changes(
        client,
        auth_headers,
        project_id,
        entity_id,
        store_id,
        updates=8,
        update_fields=["plan"],
    )

    for event in tick["events"]:
        assert event["before"]["city"] == event["after"]["city"]


def test_updating_an_unknown_field_is_refused(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    _generate(client, auth_headers, project_id, entity_id, store_id, 3)

    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/changes",
        json={"updates": 1, "update_fields": ["customer_id"]},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "customer_id" in response.json()["detail"]


def test_trimming_the_log_leaves_later_events_readable(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id, "Customer")
    identity = _field(client, auth_headers, project_id, entity_id, "customer_id")
    _field(client, auth_headers, project_id, entity_id, "city", field_type="string")
    store_id = _store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 5)
    _changes(client, auth_headers, project_id, entity_id, store_id, updates=3)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}/changes"
    trimmed = client.delete(f"{base}?before=5", headers=auth_headers).json()
    assert trimmed["removed"] == 5

    remaining = client.get(f"{base}?limit=100", headers=auth_headers).json()
    assert [e["sequence"] for e in remaining] == [5, 6, 7]


# --------------------------------------------------------------------------
# Slowly-changing dimensions
# --------------------------------------------------------------------------


def _scd2_store(client, headers, project_id, entity_id, identity_field_id, name="history"):
    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores",
        json={"name": name, "identity_field_id": identity_field_id, "scd_type": "type_2"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _customer_with_plan(client, headers, project_id):
    entity_id = _entity(client, headers, project_id, "Customer")
    identity = _field(client, headers, project_id, entity_id, "customer_id")
    _field(client, headers, project_id, entity_id, "plan", field_type="string")
    return entity_id, identity


def test_type_2_keeps_a_version_per_change_and_type_1_does_not(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    overwriting = _store(client, auth_headers, project_id, entity_id, identity, name="current")
    versioned = _scd2_store(client, auth_headers, project_id, entity_id, identity)

    for store_id in (overwriting, versioned):
        _generate(client, auth_headers, project_id, entity_id, store_id, 3)
        _changes(client, auth_headers, project_id, entity_id, store_id, updates=3)

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores"

    # Type 1 says so rather than returning an empty list, which would read
    # as "nothing ever changed".
    refused = client.get(
        f"{base}/{overwriting}/versions?at=2026-01-01T00:00:00Z", headers=auth_headers
    )
    assert refused.status_code == 400
    assert "type 2" in refused.json()["detail"]

    records = client.get(f"{base}/{versioned}/records", headers=auth_headers).json()
    one = records[0]["identity"]
    versions = client.get(
        f"{base}/{versioned}/versions?identity={one}", headers=auth_headers
    ).json()
    assert [v["version"] for v in versions] == [1, 2]
    # The first version is closed at the instant the second opens: the
    # intervals tile the timeline with no gap a query could fall into.
    assert versions[0]["valid_to"] is not None
    assert versions[0]["valid_to"] == versions[1]["valid_from"]
    assert versions[1]["valid_to"] is None


def test_a_deleted_record_closes_its_version_and_opens_no_new_one(client, auth_headers):
    """After a delete there is no truth about the record to record, which is
    a different thing from a version whose values happen to be null."""
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _scd2_store(client, auth_headers, project_id, entity_id, identity)

    _generate(client, auth_headers, project_id, entity_id, store_id, 2)
    tick = _changes(client, auth_headers, project_id, entity_id, store_id, deletes=1)
    gone = tick["events"][0]["identity"]

    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"
    versions = client.get(f"{base}/versions?identity={gone}", headers=auth_headers).json()
    assert len(versions) == 1
    assert versions[0]["valid_to"] is not None


def test_a_point_in_time_snapshot_returns_the_values_of_that_moment(client, auth_headers):
    """The question a type 2 dimension exists to answer."""
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _scd2_store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    # A history: three ticks a day apart, each changing every record.
    client.post(
        f"{base}/backfill",
        json={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-04T00:00:00Z",
            "ticks": 3,
            "inserts": 2,
            "updates": 2,
        },
        headers=auth_headers,
    )

    early = client.get(f"{base}/versions?at=2026-01-01T12:00:00Z", headers=auth_headers).json()
    late = client.get(f"{base}/versions?at=2026-01-03T12:00:00Z", headers=auth_headers).json()

    assert early, "nothing was live on the first day"
    # Each identity appears exactly once in a snapshot — that is what makes
    # it a snapshot rather than a log.
    for snapshot in (early, late):
        identities = [v["identity"] for v in snapshot]
        assert len(identities) == len(set(identities))
    # The population grew over the window, so the later snapshot is larger.
    assert len(late) > len(early)


# --------------------------------------------------------------------------
# Backfill
# --------------------------------------------------------------------------


def test_a_backfill_dates_its_events_across_the_window(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    result = client.post(
        f"{base}/backfill",
        json={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-02-01T00:00:00Z",
            "ticks": 10,
            "inserts": 2,
            "updates": 1,
        },
        headers=auth_headers,
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["events_written"] > 0
    assert body["first_event_time"].startswith("2026-01-01")

    log = client.get(f"{base}/changes?limit=1000", headers=auth_headers).json()
    times = [e["event_time"] for e in log]
    # Spread across the window, in order, and not all the same instant —
    # which is exactly what dating them "now" would have produced.
    assert times == sorted(times)
    assert len(set(times)) > 1


def test_live_generation_continues_the_backfilled_history(client, auth_headers):
    """The reason backfill belongs in the product rather than a script: the
    cursor, the identities and the change log all carry forward."""
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    filled = client.post(
        f"{base}/backfill",
        json={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-02-01T00:00:00Z",
            "ticks": 5,
            "inserts": 3,
            "updates": 2,
        },
        headers=auth_headers,
    ).json()
    historical_active = filled["total_active"]

    live = _changes(client, auth_headers, project_id, entity_id, store_id, updates=3)

    # The live tick updated records that came from the backfill, and the
    # sequence carried on rather than restarting.
    assert live["next_sequence"] > filled["next_sequence"]
    assert live["total_active"] == historical_active
    log = client.get(f"{base}/changes?limit=1000", headers=auth_headers).json()
    assert [e["sequence"] for e in log] == list(range(len(log)))


def test_a_backfill_window_cannot_run_backwards_or_into_the_future(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    backwards = client.post(
        f"{base}/backfill",
        json={
            "start": "2026-02-01T00:00:00Z",
            "end": "2026-01-01T00:00:00Z",
            "ticks": 3,
            "inserts": 1,
        },
        headers=auth_headers,
    )
    assert backwards.status_code == 400

    future = client.post(
        f"{base}/backfill",
        json={
            "start": "2099-01-01T00:00:00Z",
            "end": "2099-02-01T00:00:00Z",
            "ticks": 3,
            "inserts": 1,
        },
        headers=auth_headers,
    )
    assert future.status_code == 400
    assert "future" in future.json()["detail"]


def test_a_backfill_cannot_run_behind_changes_the_store_already_has(client, auth_headers):
    """Found by looking at the UI, not by the suite. Generating live and
    then backfilling produced SCD type 2 rows whose `valid_from` was *after*
    their `valid_to` — a record inserted today, then "updated" last week —
    and a change log whose sequence order no longer matched its event order.
    """
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _scd2_store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    # Live first — records dated now.
    _generate(client, auth_headers, project_id, entity_id, store_id, 3)

    refused = client.post(
        f"{base}/backfill",
        json={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-02-01T00:00:00Z",
            "ticks": 5,
            "updates": 2,
        },
        headers=auth_headers,
    )
    assert refused.status_code == 400
    assert "has to come first" in refused.json()["detail"]


def test_every_version_interval_runs_forwards(client, auth_headers):
    """The invariant the inverted intervals broke: a version cannot stop
    being true before it started."""
    project_id = _project(client, auth_headers)
    entity_id, identity = _customer_with_plan(client, auth_headers, project_id)
    store_id = _scd2_store(client, auth_headers, project_id, entity_id, identity)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}/record-stores/{store_id}"

    client.post(
        f"{base}/backfill",
        json={
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-03-01T00:00:00Z",
            "ticks": 8,
            "inserts": 2,
            "updates": 3,
        },
        headers=auth_headers,
    )
    # Then live churn, which must land after the whole window.
    _changes(client, auth_headers, project_id, entity_id, store_id, updates=3)

    records = client.get(f"{base}/records?limit=100", headers=auth_headers).json()
    checked = 0
    for record in records:
        versions = client.get(
            f"{base}/versions?identity={record['identity']}", headers=auth_headers
        ).json()
        for version in versions:
            if version["valid_to"] is not None:
                assert version["valid_from"] <= version["valid_to"]
                checked += 1
    assert checked > 0, "no closed versions were produced, so nothing was checked"

    log = client.get(f"{base}/changes?limit=1000", headers=auth_headers).json()
    times = [e["event_time"] for e in log]
    assert times == sorted(times), "sequence order no longer matches event order"
