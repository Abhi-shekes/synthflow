"""Phase 9: learning distributions, correlations and relationships from
real sample data.

The assertion that matters is the round trip at the bottom: profile a
sample, apply the template, generate from it, and check the *generated*
data has the same shape as the source. Everything else is a step toward
that — a fitter that names the right distribution but produces data of
the wrong shape would be worthless.
"""

import csv
import io
import json
import random
import statistics as st

import pytest

from app.services.expressions import evaluate
from app.services.profiling.distributions import fit_best
from app.services.profiling.profile import ProfileError, profile_files


def _csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode()


def _sample_csv(seed: int = 11, n: int = 1200) -> bytes:
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        age = max(18, min(90, round(rng.gauss(41, 12))))
        income = round(rng.lognormvariate(10.6, 0.5), 2)
        tier = rng.choices(["bronze", "silver", "gold"], [0.6, 0.3, 0.1])[0]
        score = round(2.5 * age + 30 + rng.gauss(0, 6), 2)
        rows.append([i, age, income, tier, score])
    return _csv(["id", "age", "income", "tier", "score"], rows)


def _profile(files, **kw):
    result, _profiles = profile_files(files, max_rows=50_000, **kw)
    return result


# ------------------------------------------------- distribution fitting


@pytest.mark.parametrize(
    ("kind", "sampler"),
    [
        ("normal", lambda r: r.gauss(50, 8)),
        ("lognormal", lambda r: r.lognormvariate(3, 0.6)),
        ("exponential", lambda r: r.expovariate(1 / 25)),
        ("uniform", lambda r: r.uniform(10, 90)),
    ],
)
def test_fitter_identifies_the_distribution_it_was_given(kind, sampler):
    rng = random.Random(3)
    values = [sampler(rng) for _ in range(3000)]
    fit = fit_best(values)
    assert fit is not None
    assert fit.kind == kind
    assert fit.quality == "close"


def test_fitter_recovers_the_parameters_not_just_the_shape():
    rng = random.Random(5)
    fit = fit_best([rng.gauss(120, 15) for _ in range(4000)])
    assert fit.kind == "normal"
    assert abs(fit.params["mean"] - 120) < 2
    assert abs(fit.params["stddev"] - 15) < 2


def test_fitter_declines_when_there_is_too_little_data():
    """Guessing a shape from a handful of points would be worse than
    saying nothing."""
    assert fit_best([1, 2, 3, 4, 5]) is None


def test_fitter_declines_on_a_constant_column():
    assert fit_best([7.0] * 200) is None


def test_fitted_expression_is_valid_and_reproduces_the_shape():
    """The fit is only useful if the expression it emits actually
    evaluates on SynthFlow's own evaluator."""
    rng = random.Random(9)
    fit = fit_best([rng.gauss(200, 25) for _ in range(3000)])
    drawn = [evaluate(fit.expression, {}) for _ in range(3000)]
    assert abs(st.mean(drawn) - 200) < 4
    assert abs(st.stdev(drawn) - 25) < 4


# ------------------------------------------------------------ profiling


def test_profile_fits_a_distribution_per_numeric_column():
    result = _profile([("customers.csv", _sample_csv())])
    fields = {f.name: f for f in result.template.entities[0].fields}

    assert "gauss(" in fields["age"].formula
    assert "lognormal(" in fields["income"].formula
    # An integer column must stay an integer.
    assert fields["age"].formula.startswith("round(")
    assert fields["age"].field_type == "integer"


def test_profile_measures_categorical_frequencies():
    result = _profile([("customers.csv", _sample_csv())])
    tier = next(f for f in result.template.entities[0].fields if f.name == "tier")

    assert tier.field_type == "enum"
    assert set(tier.enum_values) == {"bronze", "silver", "gold"}
    weights = dict(zip(tier.enum_values, tier.enum_weights, strict=True))
    # Source frequencies were 0.6 / 0.3 / 0.1.
    assert abs(weights["bronze"] - 0.6) < 0.06
    assert abs(weights["gold"] - 0.1) < 0.05
    assert abs(sum(tier.enum_weights) - 1.0) < 0.01


def test_profile_expresses_correlation_as_a_formula():
    """Fitting each column independently would reproduce both marginals
    and destroy the relationship between them."""
    result = _profile([("customers.csv", _sample_csv())])
    score = next(f for f in result.template.entities[0].fields if f.name == "score")

    assert "age" in score.formula, score.formula
    assert "noise(" in score.formula
    assert any("correlated with" in w for w in result.warnings)


def test_a_correlation_formula_only_points_at_an_earlier_field():
    """The formula engine requires it, and it's what prevents cycles."""
    result = _profile([("customers.csv", _sample_csv())])
    entity = result.template.entities[0]
    order = {f.name: f.order for f in entity.fields}
    for f in entity.fields:
        if f.formula and "age" in f.formula:
            assert order["age"] < order[f.name]


def test_profile_reproduces_the_observed_null_rate():
    """This used to be the one measured thing profiling could not
    reproduce: every nullable field got a flat 15%, and the profile said so
    in a warning. The rate now rides on the field, so there is nothing to
    apologise for."""
    rows = [[i, "" if i % 5 == 0 else i * 2] for i in range(1, 200)]
    result = _profile([("t.csv", _csv(["id", "maybe"], rows))])

    maybe = next(f for f in result.template.entities[0].fields if f.name == "maybe")
    assert maybe.null_probability == pytest.approx(0.2, abs=0.01)
    assert not any("not reproduced" in w for w in result.warnings)


def test_small_samples_fall_back_to_ranges_and_say_so():
    rows = [[i, i * 3] for i in range(1, 8)]
    result = _profile([("t.csv", _csv(["id", "n"], rows))])
    assert any("too few to fit distributions" in w for w in result.warnings)
    n = next(f for f in result.template.entities[0].fields if f.name == "n")
    assert n.formula is None
    assert n.max_value is not None


def test_low_cardinality_numbers_are_treated_as_categories():
    """A 1-5 rating is categorical; fitting a bell curve to it would be
    worse than counting its frequencies."""
    rng = random.Random(2)
    rows = [[i, rng.choices([1, 2, 3, 4, 5], [1, 1, 3, 6, 9])[0]] for i in range(1, 600)]
    result = _profile([("t.csv", _csv(["id", "rating"], rows))])
    rating = next(f for f in result.template.entities[0].fields if f.name == "rating")
    assert rating.field_type == "enum"
    assert rating.enum_weights is not None


def test_profile_rejects_an_unsupported_file():
    with pytest.raises(ProfileError):
        _profile([("notes.txt", b"nope")])


def test_profile_rejects_no_files():
    with pytest.raises(ProfileError):
        _profile([])


# ------------------------------------------- multi-file relationships


def test_related_files_are_linked_by_value_coverage():
    """Detection is by containment, not name matching — real exports are
    full of columns that don't follow a convention."""
    customers = _csv(["cid", "name"], [[i, f"c{i}"] for i in range(1, 51)])
    orders = _csv(
        ["oid", "cid", "total"],
        [[i, (i % 50) + 1, i * 1.5] for i in range(1, 300)],
    )
    result = _profile([("customers.csv", customers), ("orders.csv", orders)])

    assert {e.name for e in result.template.entities} == {"customers", "orders"}
    links = {
        (r.source_entity, r.source_field, r.target_entity, r.target_field)
        for r in result.template.relationships
    }
    assert ("orders", "cid", "customers", "cid") in links
    assert any("linked as a relationship" in w for w in result.warnings)


def test_a_small_range_column_is_not_linked_just_because_it_is_contained():
    """Regression: value containment alone linked `orders.qty` (1-13) to
    `customers.cid` (1-900) and `customers.age` to `orders.oid`, purely
    because small integers are always "contained" in a large id column.
    Found by profiling real multi-file data, not by unit tests."""
    rng = random.Random(4)
    customers = _csv(["cid", "age"], [[i, rng.randint(18, 80)] for i in range(1, 901)])
    orders = _csv(
        ["oid", "cid", "qty"],
        [[i, rng.randint(1, 900), rng.randint(1, 13)] for i in range(1, 2001)],
    )
    result = _profile([("customers.csv", customers), ("orders.csv", orders)])

    links = {
        (r.source_entity, r.source_field, r.target_entity, r.target_field)
        for r in result.template.relationships
    }
    # The real foreign key is kept...
    assert ("orders", "cid", "customers", "cid") in links
    # ...and the coincidences are not.
    assert not any(src_field == "qty" for _, src_field, _, _ in links)
    assert not any(src_field == "age" for _, src_field, _, _ in links)


def test_detected_relationships_never_form_a_cycle():
    """generate_project orders entities by dependency, so a pair that
    references each other has no valid order and fails to generate."""
    a = _csv(["aid", "bid"], [[i, i] for i in range(1, 401)])
    b = _csv(["bid", "aid"], [[i, i] for i in range(1, 401)])
    result = _profile([("a.csv", a), ("b.csv", b)])

    pairs = {(r.source_entity, r.target_entity) for r in result.template.relationships}
    assert not (("a", "b") in pairs and ("b", "a") in pairs)


def test_a_countlike_numeric_column_is_fitted_not_bucketed():
    """Regression: a quantity with ~13 distinct values was treated as
    categorical, which silently removed it from correlation detection and
    destroyed the relationship another column had with it."""
    rng = random.Random(6)
    rows = []
    for i in range(1, 1201):
        qty = max(1, round(rng.gauss(6, 2)))
        total = round(19.99 * qty + rng.gauss(0, 4), 2)
        rows.append([i, qty, total])
    result = _profile([("orders.csv", _csv(["oid", "qty", "total"], rows))])
    fields = {f.name: f for f in result.template.entities[0].fields}

    assert fields["qty"].field_type == "integer"
    assert fields["qty"].enum_values is None
    # And the correlation it drives survives.
    assert "qty" in (fields["total"].formula or "")


def test_unrelated_files_are_not_linked():
    a = _csv(["id", "v"], [[i, i] for i in range(1, 60)])
    b = _csv(["code", "w"], [[f"X{i}", i] for i in range(500, 560)])
    result = _profile([("a.csv", a), ("b.csv", b)])
    assert result.template.relationships == []


# ----------------------------------------------------------- API


def test_profile_route_returns_template_warnings_and_report(client, auth_headers):
    resp = client.post(
        "/api/v1/profile",
        files={"files": ("customers.csv", io.BytesIO(_sample_csv()), "text/csv")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template"]["entities"][0]["name"] == "customers"

    report = {r["field"]: r for r in body["report"]}
    # The report must carry real observed numbers, not placeholders.
    assert report["age"]["rows"] == 1200
    assert report["age"]["distinct"] > 10
    assert report["age"]["fit_quality"] in ("close", "approximate", "rough")
    assert report["tier"]["categories"] == 3


def test_profile_route_creates_nothing_until_applied(client, auth_headers):
    before = len(client.get("/api/v1/projects", headers=auth_headers).json())
    client.post(
        "/api/v1/profile",
        files={"files": ("customers.csv", io.BytesIO(_sample_csv()), "text/csv")},
        headers=auth_headers,
    )
    after = len(client.get("/api/v1/projects", headers=auth_headers).json())
    assert after == before


def test_profile_route_requires_auth(client):
    resp = client.post(
        "/api/v1/profile", files={"files": ("a.csv", io.BytesIO(b"a\n1\n"), "text/csv")}
    )
    assert resp.status_code == 401


def test_profile_route_rejects_a_bad_file(client, auth_headers):
    resp = client.post(
        "/api/v1/profile",
        files={"files": ("x.txt", io.BytesIO(b"nope"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ------------------------------------------------------ the round trip


def test_generated_data_matches_the_shape_of_the_source(client, auth_headers):
    """The whole point of the phase: learn from a sample, then generate
    data whose statistics match it — marginals *and* the correlation."""
    source = _sample_csv(seed=21, n=1500)
    profiled = client.post(
        "/api/v1/profile",
        files={"files": ("customers.csv", io.BytesIO(source), "text/csv")},
        headers=auth_headers,
    ).json()

    created = client.post(
        "/api/v1/projects/import", json=profiled["template"], headers=auth_headers
    )
    assert created.status_code == 201, created.text

    generated = client.post(
        f"/api/v1/projects/{created.json()['id']}/generate",
        json={"count": 1500, "counts": {}},
        headers=auth_headers,
    )
    assert generated.status_code == 200, generated.text
    rows = generated.json()["customers"]

    original = list(csv.DictReader(io.StringIO(source.decode())))
    src_age = [float(r["age"]) for r in original]
    gen_age = [float(r["age"]) for r in rows]

    # Marginal distribution of a fitted numeric column.
    assert abs(st.mean(gen_age) - st.mean(src_age)) < 3
    assert abs(st.stdev(gen_age) - st.stdev(src_age)) < 3

    # Categorical frequencies.
    def share(values, target):
        return sum(1 for v in values if v == target) / len(values)

    src_tier = [r["tier"] for r in original]
    gen_tier = [r["tier"] for r in rows]
    assert abs(share(gen_tier, "bronze") - share(src_tier, "bronze")) < 0.08

    # And the relationship between columns, which independent per-column
    # fitting would have destroyed.
    gen_score = [float(r["score"]) for r in rows]
    src_score = [float(r["score"]) for r in original]
    assert st.correlation(gen_age, gen_score) > 0.9
    assert abs(st.correlation(gen_age, gen_score) - st.correlation(src_age, src_score)) < 0.1


def test_profile_output_is_an_ordinary_editable_project(client, auth_headers):
    """No opaque learned model: the result is a normal template whose
    formulas a user can read and change."""
    profiled = client.post(
        "/api/v1/profile",
        files={"files": ("customers.csv", io.BytesIO(_sample_csv()), "text/csv")},
        headers=auth_headers,
    ).json()

    # It survives a JSON round trip and stays human-readable.
    text = json.dumps(profiled["template"])
    assert "gauss(" in text
    reparsed = json.loads(text)

    created = client.post("/api/v1/projects/import", json=reparsed, headers=auth_headers)
    assert created.status_code == 201

    entities = client.get(
        f"/api/v1/projects/{created.json()['id']}/entities", headers=auth_headers
    ).json()
    age = next(f for f in entities[0]["fields"] if f["name"] == "age")
    # Editable through the ordinary field API, like any other formula.
    patched = client.patch(
        f"/api/v1/projects/{created.json()['id']}/entities/{entities[0]['id']}/fields/{age['id']}",
        json={"formula": "round(gauss(99, 1))"},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["formula"] == "round(gauss(99, 1))"
