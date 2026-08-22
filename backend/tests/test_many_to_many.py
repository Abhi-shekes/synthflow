"""Phase 13 — many_to_many produces a real join table.

Until this phase the type was stored but generated exactly like
one_to_many: each source row drew one target value into its source field.
That is a one-to-many wearing a different label, and it is the documented
simplification these tests close.
"""

import io
import zipfile


def _project(client, headers, name="Enrolment"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()["id"]


def _entity_with_key(client, headers, project_id, name, key_name):
    entity_id = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": name}, headers=headers
    ).json()["id"]
    field_id = client.post(
        f"/api/v1/projects/{project_id}/entities/{entity_id}/fields",
        json={
            "name": key_name,
            "field_type": "uuid",
            "required": True,
            "nullable": False,
            "unique": True,
        },
        headers=headers,
    ).json()["id"]
    return entity_id, field_id


def _link(client, headers, project_id, src, src_f, tgt, tgt_f, **extra):
    response = client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "many_to_many",
            "source_entity_id": src,
            "source_field_id": src_f,
            "target_entity_id": tgt,
            "target_field_id": tgt_f,
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _setup(client, headers, **extra):
    project_id = _project(client, headers)
    student, student_key = _entity_with_key(client, headers, project_id, "Student", "student_id")
    course, course_key = _entity_with_key(client, headers, project_id, "Course", "course_id")
    _link(client, headers, project_id, student, student_key, course, course_key, **extra)
    return project_id, student, course


def _generate(client, headers, project_id, count=10):
    response = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"count": count},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_many_to_many_produces_a_join_table_alongside_the_entities(client, auth_headers):
    project_id, _, _ = _setup(client, auth_headers)
    result = _generate(client, auth_headers, project_id, count=8)

    assert "student_course" in result, sorted(result)
    links = result["student_course"]
    assert links
    assert set(links[0]) == {"student_id", "course_id"}

    students = {row["student_id"] for row in result["Student"]}
    courses = {row["course_id"] for row in result["Course"]}
    for link in links:
        assert link["student_id"] in students
        assert link["course_id"] in courses


def test_a_source_row_links_to_several_distinct_targets(client, auth_headers):
    """The thing one_to_many could not do. Distinct, because a join table
    with a duplicated pair breaks the unique constraint most schemas put on
    it."""
    project_id, _, _ = _setup(client, auth_headers, min_links=3, max_links=3)
    result = _generate(client, auth_headers, project_id, count=6)

    by_student: dict[str, list[str]] = {}
    for link in result["student_course"]:
        by_student.setdefault(link["student_id"], []).append(link["course_id"])

    assert len(by_student) == 6
    for courses in by_student.values():
        assert len(courses) == 3
        assert len(set(courses)) == 3


def test_the_link_count_varies_between_its_bounds(client, auth_headers):
    """A constant count is the tell that a dataset was generated."""
    project_id, _, _ = _setup(client, auth_headers, min_links=1, max_links=5)
    result = _generate(client, auth_headers, project_id, count=40)

    counts: dict[str, int] = {}
    for link in result["student_course"]:
        counts[link["student_id"]] = counts.get(link["student_id"], 0) + 1

    assert all(1 <= n <= 5 for n in counts.values())
    assert len(set(counts.values())) > 1, "every student got the same number of courses"


def test_asking_for_more_links_than_targets_is_capped_not_fatal(client, auth_headers):
    """Generating fewer links than requested is a smaller surprise than a
    project that refuses to generate because one entity's count is low."""
    project_id, student, course = _setup(client, auth_headers, min_links=10, max_links=10)
    response = client.post(
        f"/api/v1/projects/{project_id}/generate",
        json={"count": 5, "counts": {course: 3}},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()

    counts: dict[str, int] = {}
    for link in result["student_course"]:
        counts[link["student_id"]] = counts.get(link["student_id"], 0) + 1
    assert set(counts.values()) == {3}


def test_the_source_field_is_its_own_key_not_a_foreign_key(client, auth_headers):
    """A many-to-many has no foreign key on either side. The source's field
    must hold its own distinct keys, not values borrowed from the target."""
    project_id, _, _ = _setup(client, auth_headers)
    result = _generate(client, auth_headers, project_id, count=10)

    students = [row["student_id"] for row in result["Student"]]
    courses = {row["course_id"] for row in result["Course"]}
    assert len(set(students)) == 10
    assert not (set(students) & courses)


def test_max_links_below_min_links_is_refused(client, auth_headers):
    project_id = _project(client, auth_headers)
    student, student_key = _entity_with_key(
        client, auth_headers, project_id, "Student", "student_id"
    )
    course, course_key = _entity_with_key(client, auth_headers, project_id, "Course", "course_id")

    response = client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "many_to_many",
            "source_entity_id": student,
            "source_field_id": student_key,
            "target_entity_id": course,
            "target_field_id": course_key,
            "min_links": 5,
            "max_links": 2,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_the_join_table_is_exported_with_the_csv_zip(client, auth_headers):
    project_id, _, _ = _setup(client, auth_headers)
    response = client.post(
        f"/api/v1/projects/{project_id}/generate?format=csv",
        json={"count": 5},
        headers=auth_headers,
    )
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = set(zf.namelist())
        assert names == {"Student.csv", "Course.csv", "student_course.csv"}
        # Read it back with a real CSV reader rather than checking it is
        # non-empty: a header-only file would pass that.
        text = zf.read("student_course.csv").decode()
    assert text.splitlines()[0] == "student_id,course_id"
    assert len(text.splitlines()) > 1


def test_a_one_to_many_still_puts_the_key_on_the_row(client, auth_headers):
    """The other three types are untouched — only many_to_many changed."""
    project_id = _project(client, auth_headers)
    customer, customer_key = _entity_with_key(
        client, auth_headers, project_id, "Customer", "customer_id"
    )
    order = client.post(
        f"/api/v1/projects/{project_id}/entities", json={"name": "Order"}, headers=auth_headers
    ).json()["id"]
    order_fk = client.post(
        f"/api/v1/projects/{project_id}/entities/{order}/fields",
        json={
            "name": "customer_id",
            "field_type": "uuid",
            "required": True,
            "nullable": False,
        },
        headers=auth_headers,
    ).json()["id"]
    client.post(
        f"/api/v1/projects/{project_id}/relationships",
        json={
            "relationship_type": "one_to_many",
            "source_entity_id": order,
            "source_field_id": order_fk,
            "target_entity_id": customer,
            "target_field_id": customer_key,
        },
        headers=auth_headers,
    )

    result = _generate(client, auth_headers, project_id, count=10)
    assert "customer_order" not in result
    customers = {row["customer_id"] for row in result["Customer"]}
    assert all(row["customer_id"] in customers for row in result["Order"])
