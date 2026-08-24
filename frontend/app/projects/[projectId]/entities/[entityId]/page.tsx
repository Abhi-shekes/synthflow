"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { ChevronUp, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddErrorInjectionDialog } from "@/components/add-error-injection-dialog";
import { AddFieldDialog } from "@/components/add-field-dialog";
import { AddGeoRouteDialog } from "@/components/add-geo-route-dialog";
import { AddLookupAttachmentDialog } from "@/components/add-lookup-attachment-dialog";
import { AddTrendDialog } from "@/components/add-trend-dialog";
import { AddWorkflowDialog } from "@/components/add-workflow-dialog";
import { AppShell } from "@/components/app-shell";
import { Term } from "@/components/help/term";
import { FieldRow } from "@/components/strata/field-row";
import { DeliveryStratum } from "@/components/strata/delivery-stratum";
import { PrivacyPanel } from "@/components/strata/privacy-panel";
import { QualityReportDialog } from "@/components/quality-report-dialog";
import { Specimen } from "@/components/strata/specimen";
import { TrendPreview } from "@/components/strata/trend-preview";
import { DepthRail, Stratum, StrataProvider } from "@/components/strata/stratum";
import { Button } from "@/components/ui/button";
import {
  Panel,
  PanelBody,
  PanelEmpty,
  PanelHeader,
  PanelTitle,
} from "@/components/ui/panel";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { markChecklistStep } from "@/lib/checklist";
import { downloadBlob } from "@/lib/download";
import { fieldFill } from "@/lib/field-visual";
import { useRequireAuth } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import type {
  Entity,
  ErrorInjectionCreateInput,
  FieldCreateInput,
  GeoRouteCreateInput,
  LookupAttachmentCreateInput,
  TrendCreateInput,
  WorkflowCreateInput,
} from "@/lib/types";

interface RuleFormValues {
  condition: string;
}

interface EventTriggerFormValues {
  label: string;
  condition: string;
}


export default function EntityDetailPage() {
  const accessToken = useRequireAuth();
  const { projectId, entityId } = useParams<{ projectId: string; entityId: string }>();
  const queryClient = useQueryClient();
  const [count, setCount] = useState(10);
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);
  const ruleForm = useForm<RuleFormValues>();
  const eventTriggerForm = useForm<EventTriggerFormValues>();

  const entityQuery = useQuery({
    queryKey: ["entity", projectId, entityId],
    queryFn: () => api.getEntity(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const ruleFunctionsQuery = useQuery({
    queryKey: ["rule-functions"],
    queryFn: () => api.listRuleFunctions(accessToken!),
    enabled: !!accessToken,
  });
  const pluginRuleFunctionNames = (ruleFunctionsQuery.data ?? [])
    .filter((f) => f.source !== "builtin")
    .map((f) => f.name);

  // Which optional outputs this backend install actually supports (see
  // the backend's app/services/install.py). Used to disable a card whose

  const addField = useMutation({
    mutationFn: (field: FieldCreateInput) => api.addField(accessToken!, projectId, entityId, field),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add field"),
  });


  const generate = useMutation({
    mutationFn: () => api.generate(accessToken!, projectId, entityId, count),
    onSuccess: (data) => {
      setRows(data);
      markChecklistStep("generated");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Generation failed"),
  });

  const addRule = useMutation({
    mutationFn: (condition: string) => api.createRule(accessToken!, projectId, entityId, condition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
      ruleForm.reset();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add rule"),
  });

  const deleteRule = useMutation({
    mutationFn: (ruleId: string) => api.deleteRule(accessToken!, projectId, entityId, ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete rule"),
  });

  const addEventTrigger = useMutation({
    mutationFn: (values: EventTriggerFormValues) =>
      api.createEventTrigger(accessToken!, projectId, entityId, values.label, values.condition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
      eventTriggerForm.reset();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add event trigger"),
  });

  const deleteEventTrigger = useMutation({
    mutationFn: (eventTriggerId: string) =>
      api.deleteEventTrigger(accessToken!, projectId, entityId, eventTriggerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete event trigger"),
  });

  const addWorkflow = useMutation({
    mutationFn: (values: WorkflowCreateInput) =>
      api.createWorkflow(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add workflow"),
  });

  const deleteWorkflow = useMutation({
    mutationFn: (workflowId: string) =>
      api.deleteWorkflow(accessToken!, projectId, entityId, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete workflow"),
  });

  const addTrend = useMutation({
    mutationFn: (values: TrendCreateInput) =>
      api.createTrend(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add trend"),
  });

  const deleteTrend = useMutation({
    mutationFn: (trendId: string) => api.deleteTrend(accessToken!, projectId, entityId, trendId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete trend"),
  });

  const addErrorInjection = useMutation({
    mutationFn: (values: ErrorInjectionCreateInput) =>
      api.createErrorInjection(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add error injection"),
  });

  const deleteErrorInjection = useMutation({
    mutationFn: (errorInjectionId: string) =>
      api.deleteErrorInjection(accessToken!, projectId, entityId, errorInjectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete error injection"),
  });

  const lookupTablesQuery = useQuery({
    queryKey: ["lookup-tables", projectId],
    queryFn: () => api.listLookupTables(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const addLookupAttachment = useMutation({
    mutationFn: (values: LookupAttachmentCreateInput) =>
      api.createLookupAttachment(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add lookup"),
  });

  const deleteLookupAttachment = useMutation({
    mutationFn: (attachmentId: string) =>
      api.deleteLookupAttachment(accessToken!, projectId, entityId, attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete lookup"),
  });

  const addGeoRoute = useMutation({
    mutationFn: (values: GeoRouteCreateInput) =>
      api.createGeoRoute(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add geo route"),
  });

  const deleteGeoRoute = useMutation({
    mutationFn: (geoRouteId: string) =>
      api.deleteGeoRoute(accessToken!, projectId, entityId, geoRouteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete geo route"),
  });

  const downloadCsv = useMutation({
    mutationFn: () => api.generateCsv(accessToken!, projectId, entityId, count),
    onSuccess: (blob) => downloadBlob(blob, `${entity?.name ?? "export"}.csv`),
    onError: (error: Error) => toast.error(friendlyError(error) || "CSV export failed"),
  });

  const downloadExcel = useMutation({
    mutationFn: () => api.generateExcel(accessToken!, projectId, entityId, count),
    onSuccess: (blob) => downloadBlob(blob, `${entity?.name ?? "export"}.xlsx`),
    onError: (error: Error) => toast.error(friendlyError(error) || "Excel export failed"),
  });

  if (!accessToken) return null;

  const entity = entityQuery.data;
  // Include any extra keys generation adds beyond the declared fields (e.g. a
  // workflow field's `<field>_history`), so those are visible in the preview.
  const declaredColumns = entity?.fields.map((f) => f.name) ?? [];
  const columns =
    rows && rows.length > 0
      ? [
          ...declaredColumns,
          ...Object.keys(rows[0]).filter((k) => !declaredColumns.includes(k)),
        ]
      : declaredColumns;
  const fieldNameById = new Map(entity?.fields.map((f) => [f.id, f.name]) ?? []);
  const lookupTables = lookupTablesQuery.data ?? [];
  const lookupTableById = new Map(lookupTables.map((t) => [t.id, t]));

  return (
    <AppShell>
      <StrataProvider>
        <div className="w-full ">
          <EntityHeader
            projectId={projectId}
            entity={entity}
            onRenamed={() =>
              queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] })
            }
          />

          <div className="flex gap-8">
            <DepthRail />

            <div className="flex min-w-0 flex-1 flex-col gap-12">
              <Stratum id="shape">
                <Panel data-tour="fields-panel">
                  <PanelHeader>
                    <PanelTitle>Fields</PanelTitle>
                    <div className="flex items-center gap-2">
                                <AddFieldDialog
                        onSubmit={(v) => addField.mutate(v)}
                        isPending={addField.isPending}
                      />
                    </div>
                  </PanelHeader>
                  <PanelBody className="flex flex-col gap-3">
                    {entity?.fields.length === 0 && (
                      <PanelEmpty>
                        No fields yet. A field is one column of the generated row — add one and
                        the specimen beside you starts producing values.
                      </PanelEmpty>
                    )}
                    {entity && entity.fields.length > 0 && (
                      <>
                        {/* The core sample: the same device the system map uses
                            for an entity node, at full width. You read the
                            entity's composition before reading any of it. */}
                        <div
                          className="flex h-2 w-full gap-px overflow-hidden rounded-full"
                          aria-hidden
                        >
                          {entity.fields.map((field) => (
                            <span
                              key={field.id}
                              className="flex-1"
                              style={{ background: fieldFill(field.field_type, field.preset) }}
                            />
                          ))}
                        </div>
                        <ul className="flex flex-col gap-1.5">
                          {entity.fields.map((field) => (
                            <FieldRow
                              key={field.id}
                              projectId={projectId}
                              entityId={entityId}
                              field={field}
                              onChanged={() =>
                                queryClient.invalidateQueries({
                                  queryKey: ["entity", projectId, entityId],
                                })
                              }
                            />
                          ))}
                        </ul>
                      </>
                    )}
                  </PanelBody>
                </Panel>

                {entity && <PrivacyPanel projectId={projectId} entity={entity} />}
              </Stratum>

              <Stratum
                id="behaviour"
                hasContent={
                  !!entity &&
                  (entity.rules.length > 0 ||
                    entity.event_triggers.length > 0 ||
                    entity.workflows.length > 0 ||
                    entity.trends.length > 0 ||
                    entity.lookup_attachments.length > 0 ||
                    entity.geo_routes.length > 0)
                }
              >
            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="rule">Rules</Term></PanelTitle>
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  A rule is an expression a generated row must satisfy (e.g.{" "}
                  <code className="font-mono">temperature &gt; 60</code>); rows that
                  fail are discarded and regenerated. Can also reference{" "}
                  <code className="font-mono">RelatedEntity.field</code> for an
                  entity this one has a relationship to, but only when
                  generating the whole project.
                  {pluginRuleFunctionNames.length > 0 && (
                    <>
                      {" "}
                      From installed plugins:{" "}
                      <code className="font-mono">{pluginRuleFunctionNames.join(" ")}</code>.
                    </>
                  )}
                </p>
                <form
                  className="flex gap-2"
                  onSubmit={ruleForm.handleSubmit((v) => addRule.mutate(v.condition))}
                >
                  <Input
                    placeholder="e.g. price > 0 and quantity <= 100"
                    {...ruleForm.register("condition", { required: true })}
                  />
                  <Button type="submit" disabled={addRule.isPending}>
                    Add
                  </Button>
                </form>
                {entity?.rules.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No rules yet.</p>
                )}
                {entity && entity.rules.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.rules.map((rule) => (
                      <li
                        key={rule.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <code className="font-mono">{rule.condition}</code>
                        <Button variant="ghost" size="sm" onClick={() => deleteRule.mutate(rule.id)}>
                          Delete
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="event_trigger">Event triggers</Term></PanelTitle>
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  Unlike a rule, a matching trigger doesn&apos;t reject the row —
                  it annotates it. Every trigger whose condition is true for a
                  row appends its label to that row&apos;s{" "}
                  <code className="font-mono">_triggered_events</code> list; no
                  external notification is sent (yet). Can also reference{" "}
                  <code className="font-mono">RelatedEntity.field</code>, same
                  as a rule.
                  {pluginRuleFunctionNames.length > 0 && (
                    <>
                      {" "}
                      From installed plugins:{" "}
                      <code className="font-mono">{pluginRuleFunctionNames.join(" ")}</code>.
                    </>
                  )}
                </p>
                <form
                  className="flex gap-2"
                  onSubmit={eventTriggerForm.handleSubmit((v) => addEventTrigger.mutate(v))}
                >
                  <Input
                    placeholder="label, e.g. high_temperature"
                    className="max-w-48"
                    {...eventTriggerForm.register("label", { required: true })}
                  />
                  <Input
                    placeholder="e.g. temperature > 80"
                    {...eventTriggerForm.register("condition", { required: true })}
                  />
                  <Button type="submit" disabled={addEventTrigger.isPending}>
                    Add
                  </Button>
                </form>
                {entity?.event_triggers.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No event triggers yet.</p>
                )}
                {entity && entity.event_triggers.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.event_triggers.map((trigger) => (
                      <li
                        key={trigger.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span>
                          <span className="font-medium">{trigger.label}</span>{" "}
                          <code className="ml-1 font-mono text-muted-foreground">
                            {trigger.condition}
                          </code>
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteEventTrigger.mutate(trigger.id)}
                        >
                          Delete
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="workflow">Workflows</Term></PanelTitle>
                {entity && (
                  <AddWorkflowDialog
                    entity={entity}
                    onSubmit={(v) => addWorkflow.mutate(v)}
                    isPending={addWorkflow.isPending}
                  />
                )}
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  A workflow turns a field into a simulated state machine: instead
                  of a random value, each row gets a random walk from an initial
                  state through the transitions you define, and the walk itself is
                  included as <code className="font-mono">&lt;field&gt;_history</code>.
                </p>
                {entity?.workflows.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No workflows yet.</p>
                )}
                {entity && entity.workflows.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.workflows.map((workflow) => (
                      <li key={workflow.id} className="rounded-md border px-3 py-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{fieldNameById.get(workflow.field_id)}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteWorkflow.mutate(workflow.id)}
                          >
                            Delete
                          </Button>
                        </div>
                        <p className="mt-1 text-muted-foreground">
                          States: {workflow.states.join(", ")}
                          <br />
                          Initial: {workflow.initial_states.join(", ")}
                          <br />
                          Transitions:{" "}
                          {workflow.transitions
                            .map((t) => `${t.source}→${t.target}${t.weight !== 1 ? ` (${t.weight})` : ""}`)
                            .join(", ")}
                          {workflow.stop_probabilities && (
                            <>
                              <br />
                              Stop probabilities:{" "}
                              {Object.entries(workflow.stop_probabilities)
                                .map(([state, p]) => `${state}=${p}`)
                                .join(", ")}
                            </>
                          )}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="trend">Trends</Term></PanelTitle>
                {entity && (
                  <AddTrendDialog
                    entity={entity}
                    onSubmit={(v) => addTrend.mutate(v)}
                    isPending={addTrend.isPending}
                  />
                )}
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  Makes a numeric field&apos;s value a function of its row&apos;s
                  position within the batch (0, 1, 2, …) instead of an independent
                  random draw — e.g. a linear trend rises steadily across a
                  generated batch. Position resets to 0 on every generate call.
                </p>
                {entity?.trends.length === 0 && (
                  <PanelEmpty>
                    No trends yet. A trend turns a numeric field into a curve across the batch
                    instead of an independent random draw.
                  </PanelEmpty>
                )}
                {entity && entity.trends.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.trends.map((trend) => (
                      <li
                        key={trend.id}
                        className="flex flex-col gap-1.5 rounded-lg border border-line-soft bg-surface-2 px-3 py-2.5"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-medium">
                            {fieldNameById.get(trend.field_id)}
                          </span>
                          <span className="font-mono text-xs text-ink-faint">
                            {trend.trend_type.replaceAll("_", " ")} ·{" "}
                            {Object.entries(trend.params)
                              .map(([k, v]) => `${k}=${v}`)
                              .join(" ")}
                          </span>
                          <Button
                            variant="ghost"
                            size="xs"
                            className="ml-auto"
                            onClick={() => deleteTrend.mutate(trend.id)}
                          >
                            Delete
                          </Button>
                        </div>
                        <TrendPreview trend={trend} />
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="lookup_attachment">Lookups</Term></PanelTitle>
                {entity && (
                  <AddLookupAttachmentDialog
                    entity={entity}
                    lookupTables={lookupTables}
                    onSubmit={(v) => addLookupAttachment.mutate(v)}
                    isPending={addLookupAttachment.isPending}
                  />
                )}
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  Draws a field&apos;s value from a column of a project-level
                  lookup table instead of randomizing it — upload reference data
                  on the project page first. Unlike a relationship, this works
                  from this entity&apos;s own Generate button too, not just
                  project-wide generation.
                </p>
                {lookupTables.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">
                    No lookup tables in this project yet — upload one from the
                    project page.
                  </p>
                )}
                {entity?.lookup_attachments.length === 0 && lookupTables.length > 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No lookups attached yet.</p>
                )}
                {entity && entity.lookup_attachments.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.lookup_attachments.map((attachment) => (
                      <li
                        key={attachment.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span>
                          <span className="font-medium">
                            {fieldNameById.get(attachment.field_id)}
                          </span>
                          <span className="ml-2 text-muted-foreground">
                            ← {lookupTableById.get(attachment.lookup_table_id)?.name ?? "?"}.
                            {attachment.column}
                          </span>
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteLookupAttachment.mutate(attachment.id)}
                        >
                          Delete
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="geo_route">Geo routes</Term></PanelTitle>
                {entity && (
                  <AddGeoRouteDialog
                    entity={entity}
                    lookupTables={lookupTables}
                    onSubmit={(v) => addGeoRoute.mutate(v)}
                    isPending={addGeoRoute.isPending}
                  />
                )}
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  Makes an object/json field a {"{"}lat, lon{"}"} point walking a
                  lookup table&apos;s waypoints, interpolated across the
                  generated batch — row 0 is the route&apos;s start, the last
                  row is its end. Upload a route (a lookup table with lat/lon
                  columns) on the project page first.
                </p>
                {lookupTables.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">
                    No lookup tables in this project yet — upload one from the
                    project page.
                  </p>
                )}
                {entity?.geo_routes.length === 0 && lookupTables.length > 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No geo routes attached yet.</p>
                )}
                {entity && entity.geo_routes.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.geo_routes.map((route) => (
                      <li
                        key={route.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span>
                          <span className="font-medium">{fieldNameById.get(route.field_id)}</span>
                          <span className="ml-2 text-muted-foreground">
                            ← {lookupTableById.get(route.lookup_table_id)?.name ?? "?"} (
                            {route.lat_column}, {route.lon_column})
                          </span>
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteGeoRoute.mutate(route.id)}
                        >
                          Delete
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>
              </Stratum>

              <Stratum id="distortion" hasContent={!!entity && entity.error_injections.length > 0}>
            <Panel>
              <PanelHeader>
                <PanelTitle><Term id="error_injection">Error injection</Term></PanelTitle>
                {entity && (
                  <AddErrorInjectionDialog
                    entity={entity}
                    onSubmit={(v) => addErrorInjection.mutate(v)}
                    isPending={addErrorInjection.isPending}
                  />
                )}
              </PanelHeader>
              <PanelBody className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-ink-dim">
                  Deliberately corrupts a field&apos;s value on some fraction of
                  generated rows — nulls, empty strings, duplicates, truncated
                  text, wrong types, or out-of-range numbers — to simulate the bad
                  data a real pipeline has to handle. A rule constraining the same
                  field evaluates rows after corruption, so it can end up
                  filtering the corrupted rows back out.
                </p>
                {entity?.error_injections.length === 0 && (
                  <p className="text-xs leading-relaxed text-ink-dim">No error injections yet.</p>
                )}
                {entity && entity.error_injections.length > 0 && (
                  <ul className="flex flex-col gap-2">
                    {entity.error_injections.map((injection) => (
                      <li
                        key={injection.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span>
                          <span className="font-medium">{fieldNameById.get(injection.field_id)}</span>
                          <span className="ml-2 text-muted-foreground">
                            {Math.round(injection.rate * 100)}% ·{" "}
                            {injection.error_types.map((t) => t.replaceAll("_", " ")).join(", ")}
                          </span>
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteErrorInjection.mutate(injection.id)}
                        >
                          Delete
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </PanelBody>
            </Panel>
              </Stratum>

              <DeliveryStratum projectId={projectId} entityId={entityId} entity={entity}>
                <Panel>
                  <PanelHeader>
                    <PanelTitle>Generate</PanelTitle>
                    <QualityReportDialog projectId={projectId} entityId={entityId} />
                  </PanelHeader>
                  <PanelBody className="flex flex-col gap-4">
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={1}
                        max={5000}
                        value={count}
                        onChange={(e) => setCount(Number(e.target.value))}
                        className="w-32"
                      />
                      <Button
                        data-tour="generate-button"
                        onClick={() => generate.mutate()}
                        disabled={generate.isPending || !entity?.fields.length}
                      >
                        {generate.isPending ? "Generating…" : "Generate"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => downloadCsv.mutate()}
                        disabled={downloadCsv.isPending || !entity?.fields.length}
                      >
                        {downloadCsv.isPending ? "Preparing…" : "Download CSV"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => downloadExcel.mutate()}
                        disabled={downloadExcel.isPending || !entity?.fields.length}
                      >
                        {downloadExcel.isPending ? "Preparing…" : "Download Excel"}
                      </Button>
                    </div>

                    {rows && rows.length > 0 && (
                      <div data-tour="generated-rows" className="overflow-x-auto rounded-md border">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              {columns.map((col) => (
                                <TableHead key={col}>{col}</TableHead>
                              ))}
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {rows.map((row, i) => (
                              <TableRow key={i}>
                                {columns.map((col) => (
                                  <TableCell key={col} className="font-mono text-xs">
                                    {row[col] === null || row[col] === undefined
                                      ? "null"
                                      : typeof row[col] === "object"
                                        ? JSON.stringify(row[col])
                                        : String(row[col])}
                                  </TableCell>
                                ))}
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </PanelBody>
                </Panel>
              </DeliveryStratum>

            </div>

            {/* Pinned from xl, where there is room for a third column without
                squeezing the editor. Below that it becomes a bottom sheet —
                see SpecimenSheet. */}
            <div data-tour="specimen" className="sticky top-24 hidden h-fit w-80 shrink-0 xl:block">
              <Specimen
                projectId={projectId}
                entity={entity}
                revision={entityQuery.dataUpdatedAt}
              />
            </div>
          </div>

          <SpecimenSheet
            projectId={projectId}
            entity={entity}
            revision={entityQuery.dataUpdatedAt}
          />
        </div>
      </StrataProvider>
    </AppShell>
  );
}

/**
 * The entity's name, editable, with the delete that never existed.
 *
 * `PATCH /entities/{id}` and `DELETE /entities/{id}` have both been live since
 * Phase 1. The UI called neither, so an entity's name was fixed at creation and
 * the only way to remove one was through the API directly.
 */
function EntityHeader({
  projectId,
  entity,
  onRenamed,
}: {
  projectId: string;
  entity: Entity | undefined;
  onRenamed: () => void;
}) {
  const accessToken = useRequireAuth();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");

  const rename = useMutation({
    mutationFn: (next: string) => api.updateEntity(accessToken!, projectId, entity!.id, next),
    onSuccess: () => {
      toast.success("Renamed");
      setEditing(false);
      onRenamed();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not rename that entity"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteEntity(accessToken!, projectId, entity!.id),
    onSuccess: () => {
      toast.success("Entity deleted");
      router.replace(`/projects/${projectId}`);
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that entity"),
  });

  return (
    <header className="mb-8 flex flex-wrap items-center gap-3">
      {editing ? (
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const next = name.trim();
            if (next && next !== entity?.name) rename.mutate(next);
            else setEditing(false);
          }}
        >
          <Input
            autoFocus
            className="h-9 w-64 font-display text-lg font-bold"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <Button size="sm" type="submit" disabled={rename.isPending}>
            Save
          </Button>
          <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </form>
      ) : (
        <button
          type="button"
          disabled={!entity}
          title="Rename"
          onClick={() => {
            setName(entity?.name ?? "");
            setEditing(true);
          }}
          className="rounded-md font-display text-2xl font-bold tracking-tight decoration-line-soft underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {entity?.name ?? "…"}
        </button>
      )}

      {entity && (
        <span className="font-mono text-xs text-ink-faint">
          {entity.fields.length} field{entity.fields.length === 1 ? "" : "s"}
        </span>
      )}

      <Link
        href={`/projects/${projectId}/data`}
        className="ml-auto text-xs text-ink-dim transition-colors hover:text-ink"
      >
        Record stores &amp; jobs →
      </Link>

      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Delete entity"
        disabled={!entity || remove.isPending}
        onClick={() => {
          // Deleting an entity takes its fields, rules, workflows, outputs and
          // any stored records with it, so the confirm names the entity rather
          // than asking "are you sure?".
          if (window.confirm(`Delete "${entity?.name}" and everything attached to it?`)) {
            remove.mutate();
          }
        }}
      >
        <Trash2 />
      </Button>
    </header>
  );
}

/**
 * The specimen below xl, as a collapsible sheet docked to the bottom.
 *
 * Closed by default on small screens: there the editor already fills the
 * viewport, and a panel that permanently eats a third of it would cost more
 * than the live feedback is worth at that size.
 */
function SpecimenSheet({
  projectId,
  entity,
  revision,
}: {
  projectId: string;
  entity: Entity | undefined;
  revision: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div data-tour="specimen" className="fixed inset-x-0 bottom-0 z-20 xl:hidden">
      {open && (
        <div className="max-h-[45vh] overflow-y-auto border-t border-line bg-ground px-4 pt-3 pb-2">
          <Specimen projectId={projectId} entity={entity} revision={revision} />
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-center gap-2 border-t border-line bg-surface py-2 text-xs text-ink-dim transition-colors hover:text-ink"
      >
        <ChevronUp className={cn("size-3.5 transition-transform", open && "rotate-180")} />
        {open ? "Hide live specimen" : "Show live specimen"}
      </button>
    </div>
  );
}
