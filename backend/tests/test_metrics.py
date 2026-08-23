"""Coverage for the Prometheus instrumentation behind the monitoring
dashboard. Metrics are process-global, so every assertion here measures a
*delta* around an action rather than an absolute value — tests share one
registry and run in an arbitrary order.
"""

from prometheus_client import REGISTRY

from app.services import metrics, plugin_output_producers, stream_producers


def _sample(name: str, labels: dict[str, str] | None = None) -> float:
    value = REGISTRY.get_sample_value(name, labels or {})
    return 0.0 if value is None else value


def _create_project(client, headers, name="Metrics"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _create_entity_with_field(client, headers, project_id, name="Reading"):
    entity = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity['id']}/fields",
        json={"name": "temperature", "field_type": "integer", "required": True, "nullable": False},
        headers=headers,
    )
    return entity["id"]


def test_metrics_endpoint_is_served_without_auth(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_metrics_endpoint_exposes_every_custom_metric(client):
    body = client.get("/metrics").text
    for name in (
        "synthflow_rows_generated_total",
        "synthflow_generation_errors_total",
        "synthflow_generation_seconds",
        "synthflow_output_deliveries_total",
        "synthflow_output_delivery_errors_total",
        "synthflow_active_websocket_clients",
        "synthflow_active_producers",
    ):
        assert name in body, name


def test_metrics_endpoint_exposes_process_cpu_and_memory(client):
    """CPU/memory come free from prometheus_client's default process
    collector — the dashboard's CPU and memory panels depend on them, so
    a platform where they're missing should fail loudly here rather than
    show up as two empty panels."""
    body = client.get("/metrics").text
    assert "process_cpu_seconds_total" in body
    assert "process_resident_memory_bytes" in body


def test_unused_label_values_are_pre_seeded_at_zero(client):
    """Prometheus only knows a labelled series exists once it's been
    touched, so init_gauges() seeds every source/kind. Without this a
    dashboard shows "No data" instead of 0 for an unused output."""
    body = client.get("/metrics").text
    assert 'synthflow_rows_generated_total{source="kafka"}' in body
    assert 'synthflow_output_deliveries_total{kind="plugin"}' in body


def test_generating_rows_increments_the_api_source_counter(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    before = _sample("synthflow_rows_generated_total", {"source": "api"})
    resp = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 7},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    after = _sample("synthflow_rows_generated_total", {"source": "api"})

    assert after - before == 7


def test_project_generate_counts_rows_across_every_entity(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    _create_entity_with_field(client, auth_headers, project_id, name="A")
    _create_entity_with_field(client, auth_headers, project_id, name="B")

    before = _sample("synthflow_rows_generated_total", {"source": "api"})
    resp = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"count": 4, "counts": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    after = _sample("synthflow_rows_generated_total", {"source": "api"})

    # Two entities x 4 rows — the whole project, not just the first entity.
    assert after - before == 8


def test_rest_output_generation_is_counted_under_its_own_source(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    created = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/rest-outputs",
        json={"default_count": 3},
        headers=auth_headers,
    ).json()

    before = _sample("synthflow_rows_generated_total", {"source": "rest"})
    resp = client.get(f"/public/rest/{created['token']}")
    assert resp.status_code == 200
    after = _sample("synthflow_rows_generated_total", {"source": "rest"})

    assert after - before == 3


def test_a_failed_generation_increments_the_error_counter(client, auth_headers):
    """An unsatisfiable rule makes generate_rows raise, which the route
    turns into a 400 — the error counter should move even though the
    request itself was handled cleanly."""
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    base = f"/api/v1/projects/{project_id}/entities/{entity_id}"
    client.post(
        f"{base}/rules", json={"condition": "temperature > 999999999"}, headers=auth_headers
    )

    before = _sample("synthflow_generation_errors_total", {"source": "api"})
    resp = client.post(f"{base}/generate", json={"count": 5}, headers=auth_headers)
    assert resp.status_code == 400
    after = _sample("synthflow_generation_errors_total", {"source": "api"})

    assert after - before == 1


def test_generation_latency_histogram_records_observations(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    before = _sample("synthflow_generation_seconds_count", {"source": "api"})
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 2},
        headers=auth_headers,
    )
    after = _sample("synthflow_generation_seconds_count", {"source": "api"})

    assert after - before == 1


def test_websocket_client_gauge_rises_while_connected_and_falls_after(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    entity_id = _create_entity_with_field(client, auth_headers, project_id)
    created = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/websocket-streams",
        json={"events_per_second": 20, "batch_size": 1},
        headers=auth_headers,
    ).json()

    before = _sample("synthflow_active_websocket_clients")
    with client.websocket_connect(f"/public/stream/{created['token']}") as ws:
        ws.receive_json()
        during = _sample("synthflow_active_websocket_clients")
    after = _sample("synthflow_active_websocket_clients")

    assert during - before == 1
    assert after == before


def test_active_producer_gauges_read_the_live_task_registries(client, monkeypatch):
    """The gauges are callbacks over the producers' own `_tasks`
    registries rather than counters the producers increment, so faking
    the registry contents is enough to move them — that *is* the
    contract."""
    monkeypatch.setitem(stream_producers._task_kinds, "fake-kafka-1", "kafka")
    monkeypatch.setitem(stream_producers._task_kinds, "fake-kafka-2", "kafka")
    monkeypatch.setitem(stream_producers._task_kinds, "fake-mqtt-1", "mqtt")
    monkeypatch.setitem(plugin_output_producers._tasks, "fake-plugin-1", object())

    assert _sample("synthflow_active_producers", {"kind": "kafka"}) == 2
    assert _sample("synthflow_active_producers", {"kind": "mqtt"}) == 1
    assert _sample("synthflow_active_producers", {"kind": "plugin"}) == 1


def test_metrics_never_leak_project_entity_or_field_names(client, auth_headers):
    """The whole reason /metrics can be served unauthenticated: label
    values come from a fixed hardcoded set, never from user-controlled
    names. If someone later adds an entity-labelled metric, this fails."""
    project_id = _create_project(client, auth_headers, name="TotallyDistinctProjectName")
    entity_id = _create_entity_with_field(
        client, auth_headers, project_id, name="TotallyDistinctEntityName"
    )
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 3},
        headers=auth_headers,
    )

    body = client.get("/metrics").text
    assert "TotallyDistinctProjectName" not in body
    assert "TotallyDistinctEntityName" not in body
    assert project_id not in body
    assert entity_id not in body


def test_declared_sources_and_kinds_match_what_is_exported(client):
    """Guards the pre-seeding lists against drifting out of sync with the
    label values the code actually records."""
    body = client.get("/metrics").text
    for source in metrics.GENERATION_SOURCES:
        assert f'synthflow_rows_generated_total{{source="{source}"}}' in body, source
    for kind in metrics.PRODUCER_KINDS:
        assert f'synthflow_active_producers{{kind="{kind}"}}' in body, kind


# --- /api/v1/metrics/summary ------------------------------------------------
#
# The JSON projection the in-app live monitor reads. Same registry as
# /metrics, so the same delta-not-absolute rule applies to every assertion.


def test_summary_requires_authentication(client):
    """The whole reason this endpoint exists rather than pointing the browser
    at /metrics: that one is deliberately unauthenticated for Prometheus, and
    widening who may reach it was the alternative we rejected."""
    assert client.get("/api/v1/metrics/summary").status_code == 401


def test_summary_reports_every_generation_source(client, auth_headers):
    body = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    # Derived from the registry rather than a hardcoded list: a new source is
    # a legitimate change, and a test that fails for that says nothing about
    # whether the mechanism works.
    assert set(body["generation"]) == set(metrics.GENERATION_SOURCES)
    assert set(body["outputs"]) == set(metrics.PRODUCER_KINDS)


def test_summary_counters_move_after_generating(client, auth_headers):
    project_id = _create_project(client, auth_headers, "SummaryDelta")
    entity_id = _create_entity_with_field(client, auth_headers, project_id)

    before = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": 7},
        headers=auth_headers,
    )
    after = client.get("/api/v1/metrics/summary", headers=auth_headers).json()

    assert after["generation"]["api"]["rows"] - before["generation"]["api"]["rows"] == 7
    assert after["generation"]["api"]["calls"] - before["generation"]["api"]["calls"] == 1
    assert after["rows_total"] - before["rows_total"] == 7


def test_summary_matches_the_registry_it_projects(client, auth_headers):
    """There must be no second source of truth. If these ever disagree the
    dashboard and Grafana are showing different numbers for the same thing."""
    body = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    for source in metrics.GENERATION_SOURCES:
        assert body["generation"][source]["rows"] == _sample(
            "synthflow_rows_generated_total", {"source": source}
        )
    assert body["active_websocket_clients"] == _sample("synthflow_active_websocket_clients")


def test_summary_carries_a_server_clock_and_process_stats(client, auth_headers):
    """`captured_at` is what makes a rate derivable client-side, and it has to
    be the server's clock — the browser's would drift or be throttled."""
    body = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    assert body["captured_at"] > 0
    assert body["process"]["resident_bytes"] > 0
    assert body["process"]["start_time"] > 0
    assert body["captured_at"] >= body["process"]["start_time"]
