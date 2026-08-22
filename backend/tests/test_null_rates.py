"""Per-field null rates — closing Phase 9's one measured-but-unreproduced gap.

Profiling could always *see* that a column was 3% empty. It could not make
one: every nullable field got `generator.NULLABLE_PROBABILITY`, a flat 15%,
and the profile said so in a warning. The rate now lives on the field.

These tests are statistical, so they assert bands rather than exact counts.
The bands are wide enough that a correct implementation passes essentially
always and narrow enough that the old flat-15% behaviour fails every one of
them.
"""

import io
import json

import pytest

from app.services.generator import NULLABLE_PROBABILITY, null_probability_of


def _project(client, headers, name="Nulls"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _entity(client, headers, project_id, name="Row"):
    return client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]


def _field(client, headers, project_id, entity_id, name, **extra):
    payload = {
        "name": name,
        "field_type": "string",
        "required": False,
        "nullable": True,
        **extra,
    }
    return client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json=payload,
        headers=headers,
    )


def _generate(client, headers, project_id, entity_id, count=800):
    response = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/generate",
        json={"count": count},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _null_rate(rows, name):
    return sum(1 for r in rows if r.get(name) is None) / len(rows)


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


class _Field:
    """The three attributes `null_probability_of` reads."""

    def __init__(self, required=False, nullable=True, null_probability=None):
        self.required = required
        self.nullable = nullable
        self.null_probability = null_probability


def test_an_unset_field_keeps_the_engine_default():
    """None means "never expressed an opinion", which is what every field
    meant before this column existed — so nothing existing changes."""
    assert null_probability_of(_Field()) == NULLABLE_PROBABILITY


def test_zero_is_distinct_from_unset():
    """An explicit 0.0 means never null. Collapsing it into "unset" would
    make the one thing you cannot otherwise express impossible."""
    assert null_probability_of(_Field(null_probability=0.0)) == 0.0


def test_a_required_field_is_never_null_whatever_the_column_says():
    """The two would be a contradiction with no obvious winner, and
    "required" is the stronger statement."""
    assert null_probability_of(_Field(required=True, null_probability=0.9)) == 0.0
    assert null_probability_of(_Field(nullable=False, null_probability=0.9)) == 0.0


def test_a_rate_outside_zero_to_one_is_clamped():
    """Belt and braces — the API refuses these, but the engine is also
    reachable from an imported template and a direct service call."""
    assert null_probability_of(_Field(null_probability=1.7)) == 1.0
    assert null_probability_of(_Field(null_probability=-0.3)) == 0.0


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [0.0, 0.05, 0.4, 0.85, 1.0])
def test_generation_reproduces_the_configured_rate(client, auth_headers, rate):
    """The whole point. At 5% and at 40% the old flat 15% would have been
    wrong in opposite directions."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    _field(client, auth_headers, project_id, entity_id, "maybe", null_probability=rate)

    rows = _generate(client, auth_headers, project_id, entity_id, count=1500)
    observed = _null_rate(rows, "maybe")
    assert abs(observed - rate) < 0.05, f"wanted ~{rate}, got {observed:.3f}"


def test_an_unconfigured_field_still_generates_the_old_default(client, auth_headers):
    """Existing projects must not shift under them."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    _field(client, auth_headers, project_id, entity_id, "maybe")

    rows = _generate(client, auth_headers, project_id, entity_id, count=1500)
    assert abs(_null_rate(rows, "maybe") - NULLABLE_PROBABILITY) < 0.05


def test_two_fields_on_one_row_hold_independent_rates(client, auth_headers):
    """A per-field rate that is really per-entity would pass a single-field
    test and be useless."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    _field(client, auth_headers, project_id, entity_id, "rare", null_probability=0.05)
    _field(client, auth_headers, project_id, entity_id, "common", null_probability=0.7)

    rows = _generate(client, auth_headers, project_id, entity_id, count=1500)
    assert abs(_null_rate(rows, "rare") - 0.05) < 0.05
    assert abs(_null_rate(rows, "common") - 0.7) < 0.05


def test_a_required_field_never_generates_null(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    _field(client, auth_headers, project_id, entity_id, "always", required=True, nullable=False)

    rows = _generate(client, auth_headers, project_id, entity_id, count=400)
    assert _null_rate(rows, "always") == 0.0


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


def test_a_rate_on_a_required_field_is_refused(client, auth_headers):
    """Refused rather than ignored: a value stored and silently disregarded
    is a setting somebody will one day read back, believe, and be wrong
    about."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)

    response = _field(
        client,
        auth_headers,
        project_id,
        entity_id,
        "contradiction",
        required=True,
        nullable=False,
        null_probability=0.3,
    )
    assert response.status_code == 400
    assert "never null" in response.json()["detail"]


def test_making_a_field_required_later_is_refused_too(client, auth_headers):
    """Checked against the field as it *will* be, not as it was."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    field_id = _field(
        client, auth_headers, project_id, entity_id, "maybe", null_probability=0.3
    ).json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields/{field_id}",
        json={"required": True, "nullable": False},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_a_rate_outside_zero_to_one_is_refused_by_the_api(client, auth_headers, bad):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    response = _field(
        client, auth_headers, project_id, entity_id, "out_of_range", null_probability=bad
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Profiling — the gap this closes
# --------------------------------------------------------------------------


def _csv_with_gaps(rows: int, every: int, invert: bool = False) -> str:
    """A two-column CSV whose `value` column is empty every `every` rows.

    Two columns because an empty value in a single-column CSV is a blank
    line, and a CSV reader skips those rather than reporting a row with a
    missing cell — so a one-column fixture measures 0% nulls however many
    blanks it contains.

    `every=0` means no gaps at all. `invert` empties everything *except*
    every `every`-th row, for the almost-entirely-empty case.
    """
    lines = ["id,value"]
    for i in range(rows):
        gap = False if every == 0 else (i % every == 0)
        if invert:
            gap = not gap
        # Values repeat from a pool of 30. All-distinct values would make
        # the column `unique`, and generation then cannot mint enough
        # distinct strings to fill a batch; a pool of 30 also stays above
        # MAX_CATEGORICAL_VALUES, so the column profiles as a plain string
        # rather than an enum.
        lines.append(f"{i}," + ("" if gap else f"v{i % 30}"))
    return "\n".join(lines)


def _field_named(profiled: dict, name: str) -> dict:
    fields = profiled["template"]["entities"][0]["fields"]
    return next(f for f in fields if f["name"] == name)


def _profile_csv(client, headers, text, name="sample.csv"):
    response = client.post(
        "/api/v1/profile",
        files={"files": (name, io.BytesIO(text.encode()), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_profiling_carries_the_observed_null_rate_onto_the_field(client, auth_headers):
    """The measurement was always there; only the reproduction was missing.
    40 rows, 10 of them empty — 25%, nowhere near the old flat 15%.

    Two columns, not one: an empty value in a single-column CSV is a blank
    line, which the reader skips entirely rather than reporting as a row
    with a missing cell."""
    profiled = _profile_csv(client, auth_headers, _csv_with_gaps(40, every=4))

    field = _field_named(profiled, "value")
    assert field["nullable"] is True
    assert field["null_probability"] == pytest.approx(0.25, abs=0.01)


def test_a_column_with_no_nulls_gets_no_rate_at_all(client, auth_headers):
    """None, not 0.0 — a field that is never null has no null rate to
    express, and 0.0 would read as a choice somebody made."""
    profiled = _profile_csv(client, auth_headers, _csv_with_gaps(40, every=0))

    field = _field_named(profiled, "value")
    assert field["required"] is True
    assert field["null_probability"] is None


def test_profiling_no_longer_warns_that_the_rate_is_unreproducible(client, auth_headers):
    profiled = _profile_csv(client, auth_headers, _csv_with_gaps(40, every=4))

    joined = " ".join(profiled["warnings"])
    assert "not reproduced" not in joined
    assert "fixed 15%" not in joined


def test_an_almost_entirely_empty_column_is_still_flagged(client, auth_headers):
    """Faithfully reproducing 95% nulls is rarely what anyone wanted, even
    though it is now what happens."""
    # 95 of 100 empty.
    profiled = _profile_csv(client, auth_headers, _csv_with_gaps(100, every=20, invert=True))

    joined = " ".join(profiled["warnings"])
    assert "worth keeping" in joined


def test_a_profiled_rate_survives_into_generation(client, auth_headers):
    """End to end: measure 25% from a file, apply it, generate, count."""
    profiled = _profile_csv(client, auth_headers, _csv_with_gaps(200, every=4))

    created = client.post(
        "/api/v1/projects/import", json=profiled["template"], headers=auth_headers
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    entity_id = client.get(f"/api/v1/projects/{project_id}/entities", headers=auth_headers).json()[
        0
    ]["id"]

    generated = _generate(client, auth_headers, project_id, entity_id, count=1500)
    assert abs(_null_rate(generated, "value") - 0.25) < 0.05


# --------------------------------------------------------------------------
# Round trips
# --------------------------------------------------------------------------


def test_the_rate_survives_export_and_import(client, auth_headers):
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    _field(client, auth_headers, project_id, entity_id, "maybe", null_probability=0.42)

    template = client.get(f"/api/v1/projects/{project_id}/export", headers=auth_headers).json()
    assert template["entities"][0]["fields"][0]["null_probability"] == pytest.approx(0.42)

    reimported = client.post("/api/v1/projects/import", json=template, headers=auth_headers)
    assert reimported.status_code == 201
    new_entity = client.get(
        f"/api/v1/projects/{reimported.json()['id']}/entities", headers=auth_headers
    ).json()[0]
    assert new_entity["fields"][0]["null_probability"] == pytest.approx(0.42)


def test_the_rate_survives_a_version_rollback(client, auth_headers):
    """Version history stores the same ProjectTemplate, so this is really a
    test that nothing in that path drops the column."""
    project_id = _project(client, auth_headers)
    entity_id = _entity(client, auth_headers, project_id)
    field_id = _field(
        client, auth_headers, project_id, entity_id, "maybe", null_probability=0.42
    ).json()["id"]

    client.post(f"/api/v1/projects/{project_id}/versions", json={}, headers=auth_headers)
    client.patch(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields/{field_id}",
        json={"null_probability": 0.9},
        headers=auth_headers,
    )
    client.post(f"/api/v1/projects/{project_id}/versions/1/rollback", json={}, headers=auth_headers)

    restored = client.get(f"/api/v1/projects/{project_id}/entities", headers=auth_headers).json()[0]
    assert restored["fields"][0]["null_probability"] == pytest.approx(0.42)


def test_a_template_written_before_the_column_existed_still_imports(client, auth_headers):
    """Absent reads back as None, which takes the engine default — exactly
    what that template did when it was written."""
    legacy = {
        "name": "Legacy",
        "entities": [
            {
                "name": "Row",
                "fields": [
                    {
                        "name": "maybe",
                        "field_type": "string",
                        "order": 0,
                        "required": False,
                        "nullable": True,
                    }
                ],
            }
        ],
    }
    created = client.post(
        "/api/v1/projects/import", json=json.loads(json.dumps(legacy)), headers=auth_headers
    )
    assert created.status_code == 201, created.text
    entity = client.get(
        f"/api/v1/projects/{created.json()['id']}/entities", headers=auth_headers
    ).json()[0]
    assert entity["fields"][0]["null_probability"] is None
