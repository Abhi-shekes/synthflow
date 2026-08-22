"""Export/import a project's design as a `ProjectTemplate` (see
app.schemas.template for the format itself and the reasoning behind it).

Export walks a project's entities and their attachments and rewrites
every database id into a name-based reference. Import does the reverse:
it creates fresh rows with fresh ids and resolves each name-based
reference back to the row that was just created in *this* import, not
whatever the id pointed to in the original project. Nothing is committed
until every row has been built successfully — an import that fails
partway through (an unknown reference, an invalid enum value) leaves no
partial project behind, since the session is never committed and its
`get_db` dependency closes (rolling back) on the way out.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.error_injection import ErrorInjection, ErrorType
from app.models.event_trigger import EventTrigger
from app.models.field import EntityField, FieldType
from app.models.geo_route import GeoRoute
from app.models.lookup_attachment import LookupAttachment
from app.models.lookup_table import LookupTable
from app.models.project import Project
from app.models.relationship import Relationship, RelationshipType
from app.models.rule import Rule
from app.models.trend import Trend, TrendType
from app.models.workflow import Workflow
from app.schemas.template import (
    TEMPLATE_VERSION,
    ProjectTemplate,
    TemplateEntity,
    TemplateErrorInjection,
    TemplateEventTrigger,
    TemplateField,
    TemplateGeoRoute,
    TemplateLookupAttachment,
    TemplateLookupTable,
    TemplateRelationship,
    TemplateRule,
    TemplateTrend,
    TemplateWorkflow,
)
from app.services.error_injection import validate_error_types
from app.services.field_validation import validate_enum_weights, validate_preset
from app.services.trends import validate_params


def export_project(project: Project, db: Session) -> ProjectTemplate:
    entities = (
        db.query(Entity).filter(Entity.project_id == project.id).order_by(Entity.created_at).all()
    )
    relationships = db.query(Relationship).filter(Relationship.project_id == project.id).all()
    lookup_tables = (
        db.query(LookupTable)
        .filter(LookupTable.project_id == project.id)
        .order_by(LookupTable.created_at)
        .all()
    )

    entity_name_by_id = {e.id: e.name for e in entities}
    field_ref_by_id = {f.id: (e.name, f.name) for e in entities for f in e.fields}
    lookup_table_name_by_id = {t.id: t.name for t in lookup_tables}

    return ProjectTemplate(
        template_version=TEMPLATE_VERSION,
        name=project.name,
        description=project.description,
        entities=[
            TemplateEntity(
                name=e.name,
                fields=[
                    TemplateField(
                        name=f.name,
                        field_type=f.field_type.value,
                        order=f.order,
                        required=f.required,
                        nullable=f.nullable,
                        unique=f.unique,
                        default_value=f.default_value,
                        min_value=f.min_value,
                        max_value=f.max_value,
                        regex=f.regex,
                        preset=f.preset,
                        enum_values=f.enum_values,
                        enum_weights=f.enum_weights,
                        formula=f.formula,
                    )
                    for f in e.fields
                ],
            )
            for e in entities
        ],
        relationships=[
            TemplateRelationship(
                relationship_type=r.relationship_type.value,
                source_entity=entity_name_by_id[r.source_entity_id],
                source_field=field_ref_by_id[r.source_field_id][1],
                target_entity=entity_name_by_id[r.target_entity_id],
                target_field=field_ref_by_id[r.target_field_id][1],
            )
            for r in relationships
        ],
        rules=[
            TemplateRule(entity=e.name, condition=rule.condition)
            for e in entities
            for rule in e.rules
        ],
        event_triggers=[
            TemplateEventTrigger(entity=e.name, label=t.label, condition=t.condition)
            for e in entities
            for t in e.event_triggers
        ],
        workflows=[
            TemplateWorkflow(
                entity=e.name,
                field=field_ref_by_id[w.field_id][1],
                states=w.states,
                initial_states=w.initial_states,
                transitions=w.transitions,
                stop_probabilities=w.stop_probabilities,
            )
            for e in entities
            for w in e.workflows
        ],
        trends=[
            TemplateTrend(
                entity=e.name,
                field=field_ref_by_id[t.field_id][1],
                trend_type=t.trend_type.value,
                params=t.params,
            )
            for e in entities
            for t in e.trends
        ],
        error_injections=[
            TemplateErrorInjection(
                entity=e.name,
                field=field_ref_by_id[ei.field_id][1],
                rate=ei.rate,
                error_types=ei.error_types,
            )
            for e in entities
            for ei in e.error_injections
        ],
        lookup_tables=[
            TemplateLookupTable(name=t.name, columns=t.columns, data=t.data) for t in lookup_tables
        ],
        lookup_attachments=[
            TemplateLookupAttachment(
                entity=e.name,
                field=field_ref_by_id[a.field_id][1],
                lookup_table=lookup_table_name_by_id[a.lookup_table_id],
                column=a.column,
            )
            for e in entities
            for a in e.lookup_attachments
        ],
        geo_routes=[
            TemplateGeoRoute(
                entity=e.name,
                field=field_ref_by_id[g.field_id][1],
                lookup_table=lookup_table_name_by_id[g.lookup_table_id],
                lat_column=g.lat_column,
                lon_column=g.lon_column,
            )
            for e in entities
            for g in e.geo_routes
        ],
    )


def _resolve_entity(name: str, entities_by_name: dict[str, Entity]) -> Entity:
    entity = entities_by_name.get(name)
    if entity is None:
        raise ValueError(f"Unknown entity '{name}' referenced in template")
    return entity


def _resolve_field(
    entity_name: str, field_name: str, fields_by_ref: dict[tuple[str, str], EntityField]
) -> EntityField:
    field = fields_by_ref.get((entity_name, field_name))
    if field is None:
        raise ValueError(f"Unknown field '{entity_name}.{field_name}' referenced in template")
    return field


def _resolve_lookup_table(name: str, lookup_tables_by_name: dict[str, LookupTable]) -> LookupTable:
    table = lookup_tables_by_name.get(name)
    if table is None:
        raise ValueError(f"Unknown lookup table '{name}' referenced in template")
    return table


def import_project(template: ProjectTemplate, owner_id: uuid.UUID, db: Session) -> Project:
    """Create a new project from a template."""
    project = Project(name=template.name, description=template.description, owner_id=owner_id)
    db.add(project)
    db.flush()
    _populate(project, template, db)
    db.commit()
    db.refresh(project)
    return project


def restore_project(project: Project, template: ProjectTemplate, db: Session) -> Project:
    """Replace an existing project's contents with a template's.

    Rollback, in other words. It shares `_populate` with `import_project`
    rather than reimplementing it, because a rollback that builds a project
    slightly differently from an import is a rollback that quietly produces
    something the version never was.

    Everything the template owns is deleted first. That is what makes this a
    restore rather than a merge: a field removed in the version being rolled
    back to has to actually disappear, and reconciling two schemas
    field-by-field is a much harder problem with no obviously right answer
    for the cases where both sides changed.

    The project row itself survives, so its id, owner, organization, API
    keys and audit history are untouched — you are rolling back the design,
    not replacing the project.
    """
    for entity in list(project.entities):
        db.delete(entity)
    for relationship in db.scalars(
        select(Relationship).where(Relationship.project_id == project.id)
    ).all():
        db.delete(relationship)
    for table in db.scalars(select(LookupTable).where(LookupTable.project_id == project.id)).all():
        db.delete(table)
    # Flushed before repopulating so a name reused between the old and new
    # shape does not collide with a row that is on its way out.
    db.flush()

    project.name = template.name
    project.description = template.description
    _populate(project, template, db)
    db.commit()
    db.refresh(project)
    return project


def _populate(project: Project, template: ProjectTemplate, db: Session) -> None:
    """Build a template's contents inside an existing, empty project row."""
    entities_by_name: dict[str, Entity] = {}
    fields_by_ref: dict[tuple[str, str], EntityField] = {}
    for template_entity in template.entities:
        entity = Entity(project_id=project.id, name=template_entity.name)
        db.add(entity)
        db.flush()
        entities_by_name[template_entity.name] = entity
        for template_field in template_entity.fields:
            field_type = FieldType(template_field.field_type)
            validate_enum_weights(
                field_type, template_field.enum_values, template_field.enum_weights
            )
            validate_preset(field_type, template_field.preset, template_field.regex)

            field = EntityField(
                entity_id=entity.id,
                name=template_field.name,
                field_type=field_type,
                order=template_field.order,
                required=template_field.required,
                nullable=template_field.nullable,
                unique=template_field.unique,
                default_value=template_field.default_value,
                min_value=template_field.min_value,
                max_value=template_field.max_value,
                regex=template_field.regex,
                preset=template_field.preset,
                enum_values=template_field.enum_values,
                enum_weights=template_field.enum_weights,
                formula=template_field.formula,
            )
            db.add(field)
            db.flush()
            fields_by_ref[(template_entity.name, template_field.name)] = field

    for template_relationship in template.relationships:
        source_entity = _resolve_entity(template_relationship.source_entity, entities_by_name)
        target_entity = _resolve_entity(template_relationship.target_entity, entities_by_name)
        source_field = _resolve_field(
            template_relationship.source_entity, template_relationship.source_field, fields_by_ref
        )
        target_field = _resolve_field(
            template_relationship.target_entity, template_relationship.target_field, fields_by_ref
        )
        db.add(
            Relationship(
                project_id=project.id,
                relationship_type=RelationshipType(template_relationship.relationship_type),
                source_entity_id=source_entity.id,
                source_field_id=source_field.id,
                target_entity_id=target_entity.id,
                target_field_id=target_field.id,
            )
        )

    for template_rule in template.rules:
        entity = _resolve_entity(template_rule.entity, entities_by_name)
        db.add(Rule(entity_id=entity.id, condition=template_rule.condition))

    for template_trigger in template.event_triggers:
        entity = _resolve_entity(template_trigger.entity, entities_by_name)
        db.add(
            EventTrigger(
                entity_id=entity.id,
                label=template_trigger.label,
                condition=template_trigger.condition,
            )
        )

    workflow_fields_used: set[uuid.UUID] = set()
    for template_workflow in template.workflows:
        entity = _resolve_entity(template_workflow.entity, entities_by_name)
        field = _resolve_field(template_workflow.entity, template_workflow.field, fields_by_ref)
        if field.id in workflow_fields_used:
            raise ValueError(f"Field '{template_workflow.field}' has more than one workflow")
        workflow_fields_used.add(field.id)

        states = set(template_workflow.states)
        if not states:
            raise ValueError(f"Workflow on '{template_workflow.field}' has no states")
        if not template_workflow.initial_states:
            raise ValueError(f"Workflow on '{template_workflow.field}' has no initial_states")
        if not set(template_workflow.initial_states) <= states:
            raise ValueError(
                f"Workflow on '{template_workflow.field}': "
                "initial_states must be a subset of states"
            )
        for t in template_workflow.transitions:
            if t.get("source") not in states or t.get("target") not in states:
                raise ValueError(
                    f"Workflow on '{template_workflow.field}': transition "
                    f"{t.get('source')} -> {t.get('target')} references a state not in states"
                )
        if template_workflow.stop_probabilities:
            if not set(template_workflow.stop_probabilities) <= states:
                raise ValueError(
                    f"Workflow on '{template_workflow.field}': stop_probabilities keys "
                    "must be states"
                )
            if any(not (0 <= p <= 1) for p in template_workflow.stop_probabilities.values()):
                raise ValueError(
                    f"Workflow on '{template_workflow.field}': stop_probabilities values "
                    "must be between 0 and 1"
                )

        db.add(
            Workflow(
                entity_id=entity.id,
                field_id=field.id,
                states=template_workflow.states,
                initial_states=template_workflow.initial_states,
                transitions=template_workflow.transitions,
                stop_probabilities=template_workflow.stop_probabilities,
            )
        )

    trend_fields_used: set[uuid.UUID] = set()
    for template_trend in template.trends:
        entity = _resolve_entity(template_trend.entity, entities_by_name)
        field = _resolve_field(template_trend.entity, template_trend.field, fields_by_ref)
        if field.id in trend_fields_used:
            raise ValueError(f"Field '{template_trend.field}' has more than one trend")
        trend_fields_used.add(field.id)
        if field.field_type not in (FieldType.INTEGER, FieldType.FLOAT):
            raise ValueError(f"Trend on '{template_trend.field}': field must be integer or float")

        trend_type = TrendType(template_trend.trend_type)
        validate_params(trend_type, template_trend.params)

        db.add(
            Trend(
                entity_id=entity.id,
                field_id=field.id,
                trend_type=trend_type,
                params=template_trend.params,
            )
        )

    error_injection_fields_used: set[uuid.UUID] = set()
    for template_ei in template.error_injections:
        entity = _resolve_entity(template_ei.entity, entities_by_name)
        field = _resolve_field(template_ei.entity, template_ei.field, fields_by_ref)
        if field.id in error_injection_fields_used:
            raise ValueError(f"Field '{template_ei.field}' has more than one error injection")
        error_injection_fields_used.add(field.id)

        error_types = [ErrorType(e) for e in template_ei.error_types]
        validate_error_types(field.field_type, error_types)

        db.add(
            ErrorInjection(
                entity_id=entity.id,
                field_id=field.id,
                rate=template_ei.rate,
                error_types=template_ei.error_types,
            )
        )

    lookup_tables_by_name: dict[str, LookupTable] = {}
    for template_table in template.lookup_tables:
        table = LookupTable(
            project_id=project.id,
            name=template_table.name,
            columns=template_table.columns,
            data=template_table.data,
            row_count=len(template_table.data),
        )
        db.add(table)
        db.flush()
        lookup_tables_by_name[template_table.name] = table

    lookup_attachment_fields_used: set[uuid.UUID] = set()
    for template_attachment in template.lookup_attachments:
        entity = _resolve_entity(template_attachment.entity, entities_by_name)
        field = _resolve_field(template_attachment.entity, template_attachment.field, fields_by_ref)
        if field.id in lookup_attachment_fields_used:
            raise ValueError(f"Field '{template_attachment.field}' has more than one lookup")
        lookup_attachment_fields_used.add(field.id)
        table = _resolve_lookup_table(template_attachment.lookup_table, lookup_tables_by_name)
        if template_attachment.column not in table.columns:
            raise ValueError(
                f"'{template_attachment.column}' is not a column of lookup table "
                f"'{template_attachment.lookup_table}'"
            )

        db.add(
            LookupAttachment(
                entity_id=entity.id,
                field_id=field.id,
                lookup_table_id=table.id,
                column=template_attachment.column,
            )
        )

    geo_route_fields_used: set[uuid.UUID] = set()
    for template_route in template.geo_routes:
        entity = _resolve_entity(template_route.entity, entities_by_name)
        field = _resolve_field(template_route.entity, template_route.field, fields_by_ref)
        if field.id in geo_route_fields_used:
            raise ValueError(f"Field '{template_route.field}' has more than one geo route")
        geo_route_fields_used.add(field.id)
        if field.field_type not in (FieldType.OBJECT, FieldType.JSON):
            raise ValueError(f"Geo route on '{template_route.field}': field must be object or json")
        table = _resolve_lookup_table(template_route.lookup_table, lookup_tables_by_name)
        for column in (template_route.lat_column, template_route.lon_column):
            if column not in table.columns:
                raise ValueError(
                    f"'{column}' is not a column of lookup table '{template_route.lookup_table}'"
                )

        db.add(
            GeoRoute(
                entity_id=entity.id,
                field_id=field.id,
                lookup_table_id=table.id,
                lat_column=template_route.lat_column,
                lon_column=template_route.lon_column,
            )
        )
