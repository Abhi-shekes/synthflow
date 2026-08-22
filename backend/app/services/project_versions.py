"""Snapshots of a project's design, and what changed between two of them.

The payload is a `ProjectTemplate`, the serialisation export and import
already use. That reuse is why this was small: a separate versioning format
would have been a second thing to keep in step with the schema, and the two
would have drifted the first time a field type was added.

The diff is structural rather than textual. A JSON text diff of two
templates is technically a diff and answers no question anyone has: it
reports that a list reordered when nothing changed, and buries "the `email`
field became nullable" inside forty lines of context.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.user import User
from app.schemas.template import ProjectTemplate
from app.services.templates import export_project


class VersionError(ValueError):
    pass


def snapshot(
    db: Session, project: Project, user: User | None, label: str | None = None
) -> ProjectVersion:
    """Record the project's current design as the next version.

    The number comes from a counter on the project, not from
    `max(version) + 1` over the existing rows. Deleting the most recent
    snapshot lowers that maximum, so the next snapshot would reuse a number
    somebody may have referred to last week — "roll back to v3" would
    quietly mean a different design.
    """
    number = project.next_version_number
    project.next_version_number = number + 1
    version = ProjectVersion(
        project_id=project.id,
        version=number,
        label=label,
        template=export_project(project, db).model_dump(mode="json"),
        created_by_id=user.id if user else None,
        created_by_email=user.email if user else None,
    )
    db.add(version)
    db.flush()
    return version


def get(db: Session, project: Project, version: int) -> ProjectVersion:
    row = db.scalar(
        select(ProjectVersion).where(
            ProjectVersion.project_id == project.id, ProjectVersion.version == version
        )
    )
    if row is None:
        raise VersionError(f"This project has no version {version}")
    return row


def template_of(row: ProjectVersion) -> ProjectTemplate:
    return ProjectTemplate.model_validate(row.template)


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------

# Field attributes worth reporting a change in. Deliberately a list rather
# than "every key that differs": `order` shifts whenever a field is inserted
# above another, and reporting that as a change to every field below it
# would bury the one edit somebody actually made.
_FIELD_ATTRS = (
    "field_type",
    "required",
    "nullable",
    "unique",
    "default_value",
    "min_value",
    "max_value",
    "regex",
    "preset",
    "enum_values",
    "enum_weights",
    "formula",
)


def _fields_by_name(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["name"]: f for f in entity.get("fields", [])}


def _entities_by_name(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["name"]: e for e in template.get("entities", [])}


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """What changed between two template snapshots.

    Everything is matched **by name**, not by position or id: a template has
    no ids in it, and position moves for reasons that are not changes. The
    consequence is that renaming an entity reads as one removed and one
    added, which is honest — from the template alone there is genuinely no
    way to tell a rename from a delete-and-create.
    """
    before_entities = _entities_by_name(before)
    after_entities = _entities_by_name(after)

    added = sorted(set(after_entities) - set(before_entities))
    removed = sorted(set(before_entities) - set(after_entities))

    changed: list[dict[str, Any]] = []
    for name in sorted(set(before_entities) & set(after_entities)):
        old_fields = _fields_by_name(before_entities[name])
        new_fields = _fields_by_name(after_entities[name])

        fields_added = sorted(set(new_fields) - set(old_fields))
        fields_removed = sorted(set(old_fields) - set(new_fields))
        fields_changed = []
        for field_name in sorted(set(old_fields) & set(new_fields)):
            old = old_fields[field_name]
            new = new_fields[field_name]
            attrs = {
                attr: {"before": old.get(attr), "after": new.get(attr)}
                for attr in _FIELD_ATTRS
                if old.get(attr) != new.get(attr)
            }
            if attrs:
                fields_changed.append({"name": field_name, "changes": attrs})

        if fields_added or fields_removed or fields_changed:
            changed.append(
                {
                    "name": name,
                    "fields_added": fields_added,
                    "fields_removed": fields_removed,
                    "fields_changed": fields_changed,
                }
            )

    return {
        "name_changed": (
            None
            if before.get("name") == after.get("name")
            else {"before": before.get("name"), "after": after.get("name")}
        ),
        "entities_added": added,
        "entities_removed": removed,
        "entities_changed": changed,
        "counts": {
            section: _count_delta(before, after, section)
            for section in (
                "relationships",
                "rules",
                "event_triggers",
                "workflows",
                "trends",
                "error_injections",
                "lookup_tables",
                "lookup_attachments",
                "geo_routes",
            )
        },
    }


def _count_delta(before: dict[str, Any], after: dict[str, Any], section: str) -> dict[str, int]:
    """Counts, not contents, for the sections that hang off entities.

    A rule or a trend is identified by what it points at, and reporting
    those the way fields are reported would mean matching them on a
    composite key that the template does not promise is unique. The count
    tells you something changed and where to look; pretending to more
    precision than the format supports would be worse than that.
    """
    return {
        "before": len(before.get(section) or []),
        "after": len(after.get(section) or []),
    }


def is_empty(result: dict[str, Any]) -> bool:
    return (
        result["name_changed"] is None
        and not result["entities_added"]
        and not result["entities_removed"]
        and not result["entities_changed"]
        and all(c["before"] == c["after"] for c in result["counts"].values())
    )


def record_stores_at_risk(db: Session, project: Project) -> list[str]:
    """Entity names whose stored populations a rollback would destroy.

    A rollback deletes and rebuilds every entity, and a record store hangs
    off an entity with `ON DELETE CASCADE`. The records go with it. That is
    a real consequence of rolling back a *design*, and it is worth refusing
    to do by accident.
    """
    from app.models.continuity import RecordStore, StoredRecord

    entity_ids = [e.id for e in project.entities]
    if not entity_ids:
        return []
    # Only stores that actually hold records. An empty store is a
    # configuration a rollback can cost you; a populated one is data.
    stores = db.scalars(
        select(RecordStore)
        .where(RecordStore.entity_id.in_(entity_ids))
        .where(select(StoredRecord.id).where(StoredRecord.store_id == RecordStore.id).exists())
    ).all()
    return sorted({store.entity.name for store in stores})
