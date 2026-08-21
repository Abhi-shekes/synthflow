export type FieldType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "date"
  | "datetime"
  | "uuid"
  | "enum"
  | "array"
  | "object"
  | "json";

export const FIELD_TYPES: FieldType[] = [
  "string",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "uuid",
  "enum",
  "array",
  "object",
  "json",
];

// The preset picker (add-field-dialog.tsx) doesn't hardcode preset names —
// it fetches them from `GET /generator-plugins`, since that list can
// include generators from installed third-party plugins that a fixed
// union type can't know about (see backend app.services.plugins).
export interface GeneratorPresetSummary {
  name: string;
  source: string;
  category: "log" | "identifier" | "plugin";
}

export interface EntityField {
  id: string;
  entity_id: string;
  name: string;
  field_type: FieldType;
  order: number;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  default_value: string | null;
  min_value: number | null;
  max_value: number | null;
  regex: string | null;
  preset: string | null;
  enum_values: string[] | null;
  enum_weights: number[] | null;
  formula: string | null;
}

export interface Rule {
  id: string;
  entity_id: string;
  condition: string;
  created_at: string;
}

export interface EventTrigger {
  id: string;
  entity_id: string;
  label: string;
  condition: string;
  created_at: string;
}

export interface WorkflowTransition {
  source: string;
  target: string;
  weight?: number;
}

export interface Workflow {
  id: string;
  entity_id: string;
  field_id: string;
  states: string[];
  initial_states: string[];
  transitions: WorkflowTransition[];
  stop_probabilities: Record<string, number> | null;
  created_at: string;
}

export interface WorkflowCreateInput {
  field_id: string;
  states: string[];
  initial_states: string[];
  transitions: WorkflowTransition[];
  stop_probabilities?: Record<string, number> | null;
}

export type TrendType =
  | "linear"
  | "exponential"
  | "logistic"
  | "seasonal"
  | "cyclic"
  | "random_walk";

export const TREND_TYPES: TrendType[] = [
  "linear",
  "exponential",
  "logistic",
  "seasonal",
  "cyclic",
  "random_walk",
];

export const TREND_PARAMS: Record<TrendType, string[]> = {
  linear: ["start", "slope"],
  exponential: ["start", "rate"],
  logistic: ["capacity", "rate", "midpoint"],
  seasonal: ["base", "amplitude", "period"],
  cyclic: ["base", "amplitude", "period"],
  random_walk: ["start", "step_size"],
};

export interface Trend {
  id: string;
  entity_id: string;
  field_id: string;
  trend_type: TrendType;
  params: Record<string, number>;
  created_at: string;
}

export interface TrendCreateInput {
  field_id: string;
  trend_type: TrendType;
  params: Record<string, number>;
}

export type ErrorType =
  | "null"
  | "empty"
  | "duplicate"
  | "truncate"
  | "wrong_type"
  | "out_of_range";

export const ERROR_TYPES: ErrorType[] = [
  "null",
  "empty",
  "duplicate",
  "truncate",
  "wrong_type",
  "out_of_range",
];

// Mirrors backend app.services.error_injection._TYPE_RESTRICTIONS — which
// error types make sense for which field type. Absent from this map means
// "valid for every field type" (null, duplicate, wrong_type).
export const ERROR_TYPE_FIELD_RESTRICTIONS: Partial<Record<ErrorType, FieldType[]>> = {
  empty: ["string", "array", "object", "json"],
  truncate: ["string"],
  out_of_range: ["integer", "float"],
};

export interface ErrorInjection {
  id: string;
  entity_id: string;
  field_id: string;
  rate: number;
  error_types: ErrorType[];
  created_at: string;
}

export interface ErrorInjectionCreateInput {
  field_id: string;
  rate: number;
  error_types: ErrorType[];
}

export interface LookupTable {
  id: string;
  project_id: string;
  name: string;
  columns: string[];
  row_count: number;
  preview: Record<string, unknown>[];
  created_at: string;
}

export interface LookupAttachment {
  id: string;
  entity_id: string;
  field_id: string;
  lookup_table_id: string;
  column: string;
  created_at: string;
}

export interface LookupAttachmentCreateInput {
  field_id: string;
  lookup_table_id: string;
  column: string;
}

export interface TimelineReplay {
  id: string;
  project_id: string;
  lookup_table_id: string;
  timestamp_column: string;
  speed_multiplier: number;
  token: string;
  created_at: string;
}

export interface TimelineReplayCreateInput {
  lookup_table_id: string;
  timestamp_column: string;
  speed_multiplier: number;
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface GeoRoute {
  id: string;
  entity_id: string;
  field_id: string;
  lookup_table_id: string;
  lat_column: string;
  lon_column: string;
  created_at: string;
}

export interface GeoRouteCreateInput {
  field_id: string;
  lookup_table_id: string;
  lat_column: string;
  lon_column: string;
}

export interface Entity {
  id: string;
  project_id: string;
  name: string;
  created_at: string;
  fields: EntityField[];
  rules: Rule[];
  event_triggers: EventTrigger[];
  workflows: Workflow[];
  trends: Trend[];
  error_injections: ErrorInjection[];
  lookup_attachments: LookupAttachment[];
  geo_routes: GeoRoute[];
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
}

export interface FieldCreateInput {
  name: string;
  field_type: FieldType;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  min_value?: number | null;
  max_value?: number | null;
  regex?: string | null;
  preset?: string | null;
  enum_values?: string[] | null;
  enum_weights?: number[] | null;
  formula?: string | null;
}

export type RelationshipType = "one_to_one" | "one_to_many" | "many_to_many" | "parent_child";

export const RELATIONSHIP_TYPES: RelationshipType[] = [
  "one_to_one",
  "one_to_many",
  "many_to_many",
  "parent_child",
];

export interface Relationship {
  id: string;
  project_id: string;
  relationship_type: RelationshipType;
  source_entity_id: string;
  source_field_id: string;
  target_entity_id: string;
  target_field_id: string;
  created_at: string;
}

export interface RelationshipCreateInput {
  relationship_type: RelationshipType;
  source_entity_id: string;
  source_field_id: string;
  target_entity_id: string;
  target_field_id: string;
}

export type DatabaseDialect = "postgresql" | "mysql";

export const DATABASE_DIALECTS: DatabaseDialect[] = ["postgresql", "mysql"];

export interface DatabaseConnection {
  id: string;
  project_id: string;
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: number;
  database: string;
  username: string;
  created_at: string;
}

export interface DatabaseConnectionCreateInput {
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
}

export interface DatabaseConnectionTestResult {
  ok: boolean;
  detail: string;
}

export interface DatabasePushResult {
  table: string;
  rows_written: number;
}

export interface RestOutput {
  id: string;
  entity_id: string;
  token: string;
  default_count: number;
  created_at: string;
}

export interface WebSocketStream {
  id: string;
  entity_id: string;
  token: string;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface KafkaOutput {
  id: string;
  entity_id: string;
  bootstrap_servers: string;
  topic: string;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface KafkaOutputCreateInput {
  bootstrap_servers: string;
  topic: string;
  events_per_second: number;
  batch_size: number;
}

export interface MQTTOutput {
  id: string;
  entity_id: string;
  broker_host: string;
  broker_port: number;
  topic: string;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface MQTTOutputCreateInput {
  broker_host: string;
  broker_port: number;
  topic: string;
  events_per_second: number;
  batch_size: number;
}

export interface OutputSummary {
  type: "database" | "rest" | "websocket" | "timeline_replay" | "kafka" | "mqtt";
  id: string;
  detail: string;
}

// The "template marketplace format" — a project's design (entities,
// fields, relationships, and every simulation attachment) as one
// importable JSON document. Deliberately excludes outputs (they hold
// deployment-specific secrets) and generated data. See the backend's
// app/schemas/template.py for the full reasoning; this type just mirrors
// that shape for the export/import UI (project detail page's "Export"
// button, projects list page's "Import project" button).
export interface ProjectTemplateField {
  name: string;
  field_type: string;
  order: number;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  default_value: string | null;
  min_value: number | null;
  max_value: number | null;
  regex: string | null;
  preset: string | null;
  enum_values: string[] | null;
  enum_weights: number[] | null;
  formula: string | null;
}

export interface ProjectTemplateEntity {
  name: string;
  fields: ProjectTemplateField[];
}

export interface ProjectTemplateRelationship {
  relationship_type: string;
  source_entity: string;
  source_field: string;
  target_entity: string;
  target_field: string;
}

export interface ProjectTemplateRule {
  entity: string;
  condition: string;
}

export interface ProjectTemplateEventTrigger {
  entity: string;
  label: string;
  condition: string;
}

export interface ProjectTemplateWorkflow {
  entity: string;
  field: string;
  states: string[];
  initial_states: string[];
  transitions: Record<string, unknown>[];
  stop_probabilities: Record<string, number> | null;
}

export interface ProjectTemplateTrend {
  entity: string;
  field: string;
  trend_type: string;
  params: Record<string, unknown>;
}

export interface ProjectTemplateErrorInjection {
  entity: string;
  field: string;
  rate: number;
  error_types: string[];
}

export interface ProjectTemplateLookupTable {
  name: string;
  columns: string[];
  data: Record<string, unknown>[];
}

export interface ProjectTemplateLookupAttachment {
  entity: string;
  field: string;
  lookup_table: string;
  column: string;
}

export interface ProjectTemplateGeoRoute {
  entity: string;
  field: string;
  lookup_table: string;
  lat_column: string;
  lon_column: string;
}

export interface StarterTemplateSummary {
  key: string;
  name: string;
  description: string;
}

export interface ProjectTemplate {
  template_version: number;
  name: string;
  description: string | null;
  entities: ProjectTemplateEntity[];
  relationships: ProjectTemplateRelationship[];
  rules: ProjectTemplateRule[];
  event_triggers: ProjectTemplateEventTrigger[];
  workflows: ProjectTemplateWorkflow[];
  trends: ProjectTemplateTrend[];
  error_injections: ProjectTemplateErrorInjection[];
  lookup_tables: ProjectTemplateLookupTable[];
  lookup_attachments: ProjectTemplateLookupAttachment[];
  geo_routes: ProjectTemplateGeoRoute[];
}
