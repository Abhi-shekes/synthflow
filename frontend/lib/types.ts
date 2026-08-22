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

// Every function callable by name from a rule/event-trigger condition or
// a formula (built-ins like noise()/uniform() plus whatever rule-function
// plugins are installed) — see backend app.services.expressions.
export interface RuleFunctionSummary {
  name: string;
  source: string;
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

export type DatabaseDialect = "postgresql" | "mysql" | "mongodb";

export const DATABASE_DIALECTS: DatabaseDialect[] = ["postgresql", "mysql", "mongodb"];

// Default port per dialect, so switching the dropdown doesn't leave the
// previous dialect's port behind for the user to notice and fix.
export const DATABASE_DEFAULT_PORTS: Record<DatabaseDialect, string> = {
  postgresql: "5432",
  mysql: "3306",
  mongodb: "27017",
};

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

export interface PluginOutput {
  id: string;
  entity_id: string;
  plugin_name: string;
  config: Record<string, unknown>;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface PluginOutputCreateInput {
  plugin_name: string;
  config: Record<string, unknown>;
  events_per_second: number;
  batch_size: number;
}

// Every plugin_name currently usable on a PluginOutput — see backend
// app.services.plugins ("synthflow.outputs" entry-point group).
export interface OutputPluginSummary {
  name: string;
  source: string;
}

// What this particular backend install can actually do — see the
// backend's app/services/install.py. The entity page uses this to grey
// out an output whose optional extra isn't installed, instead of showing
// a control whose only outcome would be a 400.
export interface InstallFeature {
  key: string;
  label: string;
  description: string;
  extra: string;
  available: boolean;
}

// Phase 8: generation that happens outside the request cycle. A job
// streams rows to a file via a worker, so it isn't bounded by the
// interactive row cap — see the backend's app/services/jobs.py.
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type JobFormat = "csv" | "jsonl" | "parquet" | "orc" | "avro";

// Every one of these streams — see backend app/services/row_writers.py.
// The columnar three need an optional backend extra installed; the picker
// shows them regardless and the backend returns a clear error naming the
// extra, which is the same pattern the Kafka and MQTT outputs use.
export const JOB_FORMATS: JobFormat[] = ["csv", "jsonl", "parquet", "orc", "avro"];

export interface GenerationJob {
  id: string;
  project_id: string;
  entity_id: string | null;
  status: JobStatus;
  format: JobFormat;
  requested_rows: number;
  rows_written: number;
  artifacts: Record<string, { file: string; rows: number }> | null;
  error: string | null;
  schedule_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobSchedule {
  id: string;
  project_id: string;
  entity_id: string | null;
  name: string;
  cron: string;
  format: JobFormat;
  requested_rows: number;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  description: string;
}

export interface OutputSummary {
  type: "database" | "rest" | "websocket" | "timeline_replay" | "kafka" | "mqtt" | "plugin";
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

// Phase 7 schema import. An importer returns a template plus what it
// could not carry across — it never creates a project, so applying the
// result is a separate call to importProject(). See the backend's
// app/services/schema_import/common.py for why that split is structural.
// Phase 9: learning distributions and correlations from real data. Same
// two-step shape as schema import — a template plus what it couldn't
// carry across — with a per-column report of what was measured.
export interface ProfileColumnReport {
  entity: string;
  column: string;
  field: string;
  type: string;
  rows: number;
  missing: number;
  distinct: number;
  distribution: string | null;
  fit_quality: string | null;
  categories: number | null;
  /**
   * What kind of personal data the column appears to hold, if any.
   * `pii_redacted` says whether that was acted on — a medium-confidence
   * finding is reported for a human to judge but left alone.
   */
  pii_kind: string | null;
  pii_confidence: string | null;
  pii_redacted: boolean;
  pii_reason: string | null;
}

export interface ProfileResponse {
  template: ProjectTemplate;
  warnings: string[];
  report: ProfileColumnReport[];
}

export interface SchemaImportResponse {
  template: ProjectTemplate;
  warnings: string[];
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

/**
 * Phase 11. Three parts kept separate because they carry different
 * authority: `diagnostics` is what the engine saw while generating (the
 * only place a silent failure shows up), `violations` are the output
 * contradicting the field's own declaration (a defect, not an opinion),
 * and `assertions` are the user's own bar.
 */
export interface QualityReport {
  rows: number;
  passes: boolean;
  diagnostics: {
    rows_requested: number;
    rows_yielded: number;
    candidates_generated: number;
    candidates_discarded: number;
    discard_share: number;
    discards_by_rule: Record<string, number>;
    unique_retries: Record<string, number>;
    injections_applied: Record<string, number>;
    injections_surviving: Record<string, number>;
    injection_survival_share: Record<string, number>;
    findings: string[];
  };
  observation: {
    rows: number;
    columns: QualityColumn[];
    violations: { field: string; kind: string; detail: string }[];
    correlations: { between: string[]; correlation: number }[];
  };
  assertions: { expression: string; passed: boolean; error: string | null }[];
  available_names: string[];
}

export interface QualityColumn {
  name: string;
  declared_type: string;
  observed_type: string;
  rows: number;
  nulls: number;
  null_share: number;
  distinct: number;
  is_unique: boolean;
  min: number | null;
  max: number | null;
  mean: number | null;
  stddev: number | null;
  fitted: string | null;
  fit_quality: string | null;
  categories: Record<string, number>;
}

/** Phase 12 — an S3-compatible bucket job artifacts can be uploaded to.
 * `secret_access_key` is never returned by the API, only sent. */
export interface ObjectStorageTarget {
  id: string;
  project_id: string;
  name: string;
  provider: "s3";
  bucket: string;
  prefix: string;
  region: string;
  endpoint_url: string;
  access_key_id: string;
  created_at: string;
}

export interface ObjectStorageTargetCreateInput {
  name: string;
  bucket: string;
  prefix?: string;
  region?: string;
  endpoint_url?: string;
  access_key_id: string;
  secret_access_key: string;
}

export interface ObjectStorageTestResult {
  ok: boolean;
  detail: string;
}

/** Phase 12 — publishes to a RabbitMQ exchange. `password` is write-only. */
export interface RabbitMQOutput {
  id: string;
  entity_id: string;
  host: string;
  port: number;
  vhost: string;
  username: string;
  exchange: string;
  routing_key: string;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface RabbitMQOutputCreateInput {
  host: string;
  port?: number;
  vhost?: string;
  username?: string;
  password?: string;
  exchange?: string;
  routing_key: string;
  events_per_second?: number;
  batch_size?: number;
}

/** Phase 12 — POSTs signed batches to a URL. `secret` is write-only. */
export interface WebhookOutput {
  id: string;
  entity_id: string;
  url: string;
  events_per_second: number;
  batch_size: number;
  created_at: string;
}

export interface WebhookOutputCreateInput {
  url: string;
  secret: string;
  events_per_second?: number;
  batch_size?: number;
}

/** Phase 12 — learn from data SynthFlow fetches itself. Exactly one of
 * `urls`, `object_keys` or `tables` is sent. `project_id` is required for
 * the two that need credentials, and omitted for a public URL. */
export interface ProfileSourceRequest {
  project_id?: string;
  project_name?: string | null;
  urls?: string[];
  storage_target_id?: string;
  object_keys?: string[];
  connection_id?: string;
  tables?: string[];
}

/** Phase 13 — a population of records for one entity that survives between
 * generation calls. `position` is the cursor trends and geo routes read, so
 * a curve continues across calls instead of replaying from its start. */
export interface RecordStore {
  id: string;
  entity_id: string;
  name: string;
  identity_field_id: string;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface RecordStoreStats extends RecordStore {
  active_records: number;
  deleted_records: number;
}

export interface StoredRecord {
  id: string;
  identity: string;
  data: Record<string, unknown>;
  version: number;
  status: "active" | "deleted";
  created_at: string;
  updated_at: string;
}

export interface RecordStoreCreateInput {
  name: string;
  identity_field_id: string;
}

export interface GenerateIntoStoreResponse {
  rows: Record<string, unknown>[];
  position: number;
  total_active: number;
}
