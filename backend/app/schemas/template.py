"""The "template marketplace format" from the roadmap: a project's
*design* — entities, fields, relationships, and every simulation
attachment (rules, event triggers, workflows, trends, error injections,
lookup tables + attachments, geo routes) — serialized as one importable
JSON document. See app.services.templates for the export/import logic
this schema is shaped for.

Everything here is looked up by *name*, not database id: an exported
template has to survive being handed to someone else's SynthFlow
instance, where the original UUIDs mean nothing. This is also what makes
a template hand-editable — a "starter template" is just a JSON file that
matches this shape, not a database dump. If a project has two fields
with the same name on the same entity (something the app doesn't
prevent, since nothing else relies on name uniqueness either — a
formula/rule expression already can't disambiguate them), export/import
resolves references to the first match; this is a pre-existing ambiguity
in the data model, not one this format introduces.

Deliberately excluded: outputs (DatabaseConnection, RestOutput,
WebSocketStream, KafkaOutput, MQTTOutput) and generated data itself.
Outputs hold deployment-specific secrets/addresses (a broker host, a
database password) that have no meaning on whoever's importing this
template, and reintroducing them under someone else's credentials isn't
something the app can do safely on its own — the recipient wires up their
own outputs after import, the same as they'd do for a hand-built project.
"""

from pydantic import BaseModel

TEMPLATE_VERSION = 1


class TemplateField(BaseModel):
    name: str
    field_type: str
    order: int = 0
    required: bool = False
    nullable: bool = True
    unique: bool = False
    # Carried through export, import and version history so a profiled
    # project's observed null rates survive a round trip. Absent in
    # templates written before this existed, which read back as None and so
    # take the engine default — exactly what they did when they were made.
    null_probability: float | None = None
    default_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    preset: str | None = None
    enum_values: list[str] | None = None
    enum_weights: list[float] | None = None
    formula: str | None = None


class TemplateEntity(BaseModel):
    name: str
    fields: list[TemplateField] = []


class TemplateRelationship(BaseModel):
    relationship_type: str
    source_entity: str
    source_field: str
    target_entity: str
    target_field: str


class TemplateRule(BaseModel):
    entity: str
    condition: str


class TemplateEventTrigger(BaseModel):
    entity: str
    label: str
    condition: str


class TemplateWorkflow(BaseModel):
    entity: str
    field: str
    states: list[str]
    initial_states: list[str]
    transitions: list[dict]
    stop_probabilities: dict | None = None


class TemplateTrend(BaseModel):
    entity: str
    field: str
    trend_type: str
    params: dict


class TemplateErrorInjection(BaseModel):
    entity: str
    field: str
    rate: float
    error_types: list[str]


class TemplateLookupTable(BaseModel):
    name: str
    columns: list[str]
    data: list[dict]


class TemplateLookupAttachment(BaseModel):
    entity: str
    field: str
    lookup_table: str
    column: str


class TemplateGeoRoute(BaseModel):
    entity: str
    field: str
    lookup_table: str
    lat_column: str
    lon_column: str


class ProjectTemplate(BaseModel):
    template_version: int = TEMPLATE_VERSION
    name: str
    description: str | None = None
    entities: list[TemplateEntity] = []
    relationships: list[TemplateRelationship] = []
    rules: list[TemplateRule] = []
    event_triggers: list[TemplateEventTrigger] = []
    workflows: list[TemplateWorkflow] = []
    trends: list[TemplateTrend] = []
    error_injections: list[TemplateErrorInjection] = []
    lookup_tables: list[TemplateLookupTable] = []
    lookup_attachments: list[TemplateLookupAttachment] = []
    geo_routes: list[TemplateGeoRoute] = []


class StarterTemplateSummary(BaseModel):
    """Metadata for one bundled starter template — see
    app.services.starter_templates. Kept separate from ProjectTemplate so
    the gallery listing (`GET /starter-templates`) doesn't have to ship
    every template's full entity/field payload just to render a card."""

    key: str
    name: str
    description: str
