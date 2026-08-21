import type {
  DatabaseConnection,
  DatabaseConnectionCreateInput,
  DatabaseConnectionTestResult,
  DatabasePushResult,
  Entity,
  ErrorInjection,
  ErrorInjectionCreateInput,
  EventTrigger,
  FieldCreateInput,
  GeneratorPresetSummary,
  GeoRoute,
  GeoRouteCreateInput,
  InstallFeature,
  KafkaOutput,
  KafkaOutputCreateInput,
  LookupAttachment,
  LookupAttachmentCreateInput,
  LookupTable,
  MQTTOutput,
  MQTTOutputCreateInput,
  OutputPluginSummary,
  OutputSummary,
  PluginOutput,
  PluginOutputCreateInput,
  Project,
  ProjectTemplate,
  Relationship,
  RelationshipCreateInput,
  RestOutput,
  Rule,
  RuleFunctionSummary,
  StarterTemplateSummary,
  TimelineReplay,
  TimelineReplayCreateInput,
  Trend,
  TrendCreateInput,
  User,
  WebSocketStream,
  Workflow,
  WorkflowCreateInput,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function requestBlob(
  path: string,
  options: RequestInit,
  token: string
): Promise<Blob> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

async function requestUpload<T>(path: string, formData: FormData, token: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export const api = {
  signup: (email: string, password: string) =>
    request<User>("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: (token: string) => request<User>("/api/v1/auth/me", {}, token),

  listProjects: (token: string) => request<Project[]>("/api/v1/projects", {}, token),

  createProject: (token: string, data: { name: string; description?: string }) =>
    request<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(data) }, token),

  getProject: (token: string, id: string) =>
    request<Project>(`/api/v1/projects/${id}`, {}, token),

  deleteProject: (token: string, id: string) =>
    request<void>(`/api/v1/projects/${id}`, { method: "DELETE" }, token),

  listEntities: (token: string, projectId: string) =>
    request<Entity[]>(`/api/v1/projects/${projectId}/entities`, {}, token),

  createEntity: (token: string, projectId: string, name: string) =>
    request<Entity>(
      `/api/v1/projects/${projectId}/entities`,
      { method: "POST", body: JSON.stringify({ name }) },
      token
    ),

  getEntity: (token: string, projectId: string, entityId: string) =>
    request<Entity>(`/api/v1/projects/${projectId}/entities/${entityId}`, {}, token),

  deleteEntity: (token: string, projectId: string, entityId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}`,
      { method: "DELETE" },
      token
    ),

  addField: (token: string, projectId: string, entityId: string, field: FieldCreateInput) =>
    request(
      `/api/v1/projects/${projectId}/entities/${entityId}/fields`,
      { method: "POST", body: JSON.stringify(field) },
      token
    ),

  deleteField: (token: string, projectId: string, entityId: string, fieldId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/fields/${fieldId}`,
      { method: "DELETE" },
      token
    ),

  generate: (token: string, projectId: string, entityId: string, count: number) =>
    request<Record<string, unknown>[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/generate`,
      { method: "POST", body: JSON.stringify({ count }) },
      token
    ),

  generateCsv: (token: string, projectId: string, entityId: string, count: number) =>
    requestBlob(
      `/api/v1/projects/${projectId}/entities/${entityId}/generate?format=csv`,
      { method: "POST", body: JSON.stringify({ count }) },
      token
    ),

  generateExcel: (token: string, projectId: string, entityId: string, count: number) =>
    requestBlob(
      `/api/v1/projects/${projectId}/entities/${entityId}/generate?format=xlsx`,
      { method: "POST", body: JSON.stringify({ count }) },
      token
    ),

  listRelationships: (token: string, projectId: string) =>
    request<Relationship[]>(`/api/v1/projects/${projectId}/relationships`, {}, token),

  createRelationship: (token: string, projectId: string, data: RelationshipCreateInput) =>
    request<Relationship>(
      `/api/v1/projects/${projectId}/relationships`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteRelationship: (token: string, projectId: string, relationshipId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/relationships/${relationshipId}`,
      { method: "DELETE" },
      token
    ),

  generateProject: (
    token: string,
    projectId: string,
    count: number,
    counts: Record<string, number> = {}
  ) =>
    request<Record<string, Record<string, unknown>[]>>(
      `/api/v1/projects/${projectId}/generate`,
      { method: "POST", body: JSON.stringify({ count, counts }) },
      token
    ),

  generateProjectCsvZip: (token: string, projectId: string, count: number) =>
    requestBlob(
      `/api/v1/projects/${projectId}/generate?format=csv`,
      { method: "POST", body: JSON.stringify({ count, counts: {} }) },
      token
    ),

  generateProjectExcel: (token: string, projectId: string, count: number) =>
    requestBlob(
      `/api/v1/projects/${projectId}/generate?format=xlsx`,
      { method: "POST", body: JSON.stringify({ count, counts: {} }) },
      token
    ),

  listRules: (token: string, projectId: string, entityId: string) =>
    request<Rule[]>(`/api/v1/projects/${projectId}/entities/${entityId}/rules`, {}, token),

  createRule: (token: string, projectId: string, entityId: string, condition: string) =>
    request<Rule>(
      `/api/v1/projects/${projectId}/entities/${entityId}/rules`,
      { method: "POST", body: JSON.stringify({ condition }) },
      token
    ),

  deleteRule: (token: string, projectId: string, entityId: string, ruleId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/rules/${ruleId}`,
      { method: "DELETE" },
      token
    ),

  listEventTriggers: (token: string, projectId: string, entityId: string) =>
    request<EventTrigger[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/event-triggers`,
      {},
      token
    ),

  createEventTrigger: (
    token: string,
    projectId: string,
    entityId: string,
    label: string,
    condition: string
  ) =>
    request<EventTrigger>(
      `/api/v1/projects/${projectId}/entities/${entityId}/event-triggers`,
      { method: "POST", body: JSON.stringify({ label, condition }) },
      token
    ),

  deleteEventTrigger: (token: string, projectId: string, entityId: string, eventTriggerId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/event-triggers/${eventTriggerId}`,
      { method: "DELETE" },
      token
    ),

  listWorkflows: (token: string, projectId: string, entityId: string) =>
    request<Workflow[]>(`/api/v1/projects/${projectId}/entities/${entityId}/workflows`, {}, token),

  createWorkflow: (
    token: string,
    projectId: string,
    entityId: string,
    data: WorkflowCreateInput
  ) =>
    request<Workflow>(
      `/api/v1/projects/${projectId}/entities/${entityId}/workflows`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteWorkflow: (token: string, projectId: string, entityId: string, workflowId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/workflows/${workflowId}`,
      { method: "DELETE" },
      token
    ),

  listDatabaseConnections: (token: string, projectId: string) =>
    request<DatabaseConnection[]>(
      `/api/v1/projects/${projectId}/database-connections`,
      {},
      token
    ),

  createDatabaseConnection: (
    token: string,
    projectId: string,
    data: DatabaseConnectionCreateInput
  ) =>
    request<DatabaseConnection>(
      `/api/v1/projects/${projectId}/database-connections`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteDatabaseConnection: (token: string, projectId: string, connectionId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/database-connections/${connectionId}`,
      { method: "DELETE" },
      token
    ),

  testDatabaseConnection: (token: string, projectId: string, connectionId: string) =>
    request<DatabaseConnectionTestResult>(
      `/api/v1/projects/${projectId}/database-connections/${connectionId}/test`,
      { method: "POST" },
      token
    ),

  pushToDatabaseConnection: (
    token: string,
    projectId: string,
    connectionId: string,
    entityId: string,
    count: number,
    tableName?: string
  ) =>
    request<DatabasePushResult>(
      `/api/v1/projects/${projectId}/database-connections/${connectionId}/push`,
      {
        method: "POST",
        body: JSON.stringify({ entity_id: entityId, count, table_name: tableName || null }),
      },
      token
    ),

  listRestOutputs: (token: string, projectId: string, entityId: string) =>
    request<RestOutput[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/rest-outputs`,
      {},
      token
    ),

  createRestOutput: (token: string, projectId: string, entityId: string, defaultCount: number) =>
    request<RestOutput>(
      `/api/v1/projects/${projectId}/entities/${entityId}/rest-outputs`,
      { method: "POST", body: JSON.stringify({ default_count: defaultCount }) },
      token
    ),

  deleteRestOutput: (token: string, projectId: string, entityId: string, outputId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/rest-outputs/${outputId}`,
      { method: "DELETE" },
      token
    ),

  listOutputs: (token: string, projectId: string) =>
    request<OutputSummary[]>(`/api/v1/projects/${projectId}/outputs`, {}, token),

  listWebSocketStreams: (token: string, projectId: string, entityId: string) =>
    request<WebSocketStream[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/websocket-streams`,
      {},
      token
    ),

  createWebSocketStream: (
    token: string,
    projectId: string,
    entityId: string,
    eventsPerSecond: number,
    batchSize: number
  ) =>
    request<WebSocketStream>(
      `/api/v1/projects/${projectId}/entities/${entityId}/websocket-streams`,
      {
        method: "POST",
        body: JSON.stringify({ events_per_second: eventsPerSecond, batch_size: batchSize }),
      },
      token
    ),

  deleteWebSocketStream: (token: string, projectId: string, entityId: string, streamId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/websocket-streams/${streamId}`,
      { method: "DELETE" },
      token
    ),

  listTrends: (token: string, projectId: string, entityId: string) =>
    request<Trend[]>(`/api/v1/projects/${projectId}/entities/${entityId}/trends`, {}, token),

  createTrend: (token: string, projectId: string, entityId: string, data: TrendCreateInput) =>
    request<Trend>(
      `/api/v1/projects/${projectId}/entities/${entityId}/trends`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteTrend: (token: string, projectId: string, entityId: string, trendId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/trends/${trendId}`,
      { method: "DELETE" },
      token
    ),

  listErrorInjections: (token: string, projectId: string, entityId: string) =>
    request<ErrorInjection[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/error-injections`,
      {},
      token
    ),

  createErrorInjection: (
    token: string,
    projectId: string,
    entityId: string,
    data: ErrorInjectionCreateInput
  ) =>
    request<ErrorInjection>(
      `/api/v1/projects/${projectId}/entities/${entityId}/error-injections`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteErrorInjection: (
    token: string,
    projectId: string,
    entityId: string,
    errorInjectionId: string
  ) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/error-injections/${errorInjectionId}`,
      { method: "DELETE" },
      token
    ),

  listLookupTables: (token: string, projectId: string) =>
    request<LookupTable[]>(`/api/v1/projects/${projectId}/lookup-tables`, {}, token),

  createLookupTable: (token: string, projectId: string, name: string, file: File) => {
    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);
    return requestUpload<LookupTable>(
      `/api/v1/projects/${projectId}/lookup-tables`,
      formData,
      token
    );
  },

  deleteLookupTable: (token: string, projectId: string, lookupTableId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/lookup-tables/${lookupTableId}`,
      { method: "DELETE" },
      token
    ),

  listLookupAttachments: (token: string, projectId: string, entityId: string) =>
    request<LookupAttachment[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/lookup-attachments`,
      {},
      token
    ),

  createLookupAttachment: (
    token: string,
    projectId: string,
    entityId: string,
    data: LookupAttachmentCreateInput
  ) =>
    request<LookupAttachment>(
      `/api/v1/projects/${projectId}/entities/${entityId}/lookup-attachments`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteLookupAttachment: (
    token: string,
    projectId: string,
    entityId: string,
    attachmentId: string
  ) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/lookup-attachments/${attachmentId}`,
      { method: "DELETE" },
      token
    ),

  listTimelineReplays: (token: string, projectId: string) =>
    request<TimelineReplay[]>(`/api/v1/projects/${projectId}/timeline-replays`, {}, token),

  createTimelineReplay: (
    token: string,
    projectId: string,
    data: TimelineReplayCreateInput
  ) =>
    request<TimelineReplay>(
      `/api/v1/projects/${projectId}/timeline-replays`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteTimelineReplay: (token: string, projectId: string, replayId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/timeline-replays/${replayId}`,
      { method: "DELETE" },
      token
    ),

  listGeoRoutes: (token: string, projectId: string, entityId: string) =>
    request<GeoRoute[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/geo-routes`,
      {},
      token
    ),

  createGeoRoute: (
    token: string,
    projectId: string,
    entityId: string,
    data: GeoRouteCreateInput
  ) =>
    request<GeoRoute>(
      `/api/v1/projects/${projectId}/entities/${entityId}/geo-routes`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteGeoRoute: (token: string, projectId: string, entityId: string, geoRouteId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/geo-routes/${geoRouteId}`,
      { method: "DELETE" },
      token
    ),

  listKafkaOutputs: (token: string, projectId: string, entityId: string) =>
    request<KafkaOutput[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/kafka-outputs`,
      {},
      token
    ),

  createKafkaOutput: (
    token: string,
    projectId: string,
    entityId: string,
    data: KafkaOutputCreateInput
  ) =>
    request<KafkaOutput>(
      `/api/v1/projects/${projectId}/entities/${entityId}/kafka-outputs`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteKafkaOutput: (token: string, projectId: string, entityId: string, outputId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/kafka-outputs/${outputId}`,
      { method: "DELETE" },
      token
    ),

  listMqttOutputs: (token: string, projectId: string, entityId: string) =>
    request<MQTTOutput[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/mqtt-outputs`,
      {},
      token
    ),

  createMqttOutput: (
    token: string,
    projectId: string,
    entityId: string,
    data: MQTTOutputCreateInput
  ) =>
    request<MQTTOutput>(
      `/api/v1/projects/${projectId}/entities/${entityId}/mqtt-outputs`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deleteMqttOutput: (token: string, projectId: string, entityId: string, outputId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/mqtt-outputs/${outputId}`,
      { method: "DELETE" },
      token
    ),

  listPluginOutputs: (token: string, projectId: string, entityId: string) =>
    request<PluginOutput[]>(
      `/api/v1/projects/${projectId}/entities/${entityId}/plugin-outputs`,
      {},
      token
    ),

  createPluginOutput: (
    token: string,
    projectId: string,
    entityId: string,
    data: PluginOutputCreateInput
  ) =>
    request<PluginOutput>(
      `/api/v1/projects/${projectId}/entities/${entityId}/plugin-outputs`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),

  deletePluginOutput: (token: string, projectId: string, entityId: string, outputId: string) =>
    request<void>(
      `/api/v1/projects/${projectId}/entities/${entityId}/plugin-outputs/${outputId}`,
      { method: "DELETE" },
      token
    ),

  listInstallConfig: (token: string) =>
    request<InstallFeature[]>("/api/v1/install-config", {}, token),

  listOutputPlugins: (token: string) =>
    request<OutputPluginSummary[]>("/api/v1/output-plugins", {}, token),

  listGeneratorPlugins: (token: string) =>
    request<GeneratorPresetSummary[]>("/api/v1/generator-plugins", {}, token),

  listRuleFunctions: (token: string) =>
    request<RuleFunctionSummary[]>("/api/v1/rule-functions", {}, token),

  exportProject: (token: string, projectId: string) =>
    request<ProjectTemplate>(`/api/v1/projects/${projectId}/export`, {}, token),

  importProject: (token: string, template: ProjectTemplate) =>
    request<Project>(
      "/api/v1/projects/import",
      { method: "POST", body: JSON.stringify(template) },
      token
    ),

  listStarterTemplates: (token: string) =>
    request<StarterTemplateSummary[]>("/api/v1/starter-templates", {}, token),

  getStarterTemplate: (token: string, key: string) =>
    request<ProjectTemplate>(`/api/v1/starter-templates/${key}`, {}, token),
};
