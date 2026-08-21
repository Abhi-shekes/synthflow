"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddErrorInjectionDialog } from "@/components/add-error-injection-dialog";
import { AddFieldDialog } from "@/components/add-field-dialog";
import { AddLookupAttachmentDialog } from "@/components/add-lookup-attachment-dialog";
import { AddTrendDialog } from "@/components/add-trend-dialog";
import { AddWorkflowDialog } from "@/components/add-workflow-dialog";
import { AppShell } from "@/components/app-shell";
import { StreamPreview } from "@/components/stream-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { useRequireAuth } from "@/lib/hooks";
import type {
  ErrorInjectionCreateInput,
  FieldCreateInput,
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const WS_URL = API_URL.replace(/^http/, "ws");

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

  const addField = useMutation({
    mutationFn: (field: FieldCreateInput) => api.addField(accessToken!, projectId, entityId, field),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add field"),
  });

  const deleteField = useMutation({
    mutationFn: (fieldId: string) => api.deleteField(accessToken!, projectId, entityId, fieldId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete field"),
  });

  const generate = useMutation({
    mutationFn: () => api.generate(accessToken!, projectId, entityId, count),
    onSuccess: (data) => setRows(data),
    onError: (error: Error) => toast.error(error.message || "Generation failed"),
  });

  const addRule = useMutation({
    mutationFn: (condition: string) => api.createRule(accessToken!, projectId, entityId, condition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
      ruleForm.reset();
    },
    onError: (error: Error) => toast.error(error.message || "Could not add rule"),
  });

  const deleteRule = useMutation({
    mutationFn: (ruleId: string) => api.deleteRule(accessToken!, projectId, entityId, ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete rule"),
  });

  const addEventTrigger = useMutation({
    mutationFn: (values: EventTriggerFormValues) =>
      api.createEventTrigger(accessToken!, projectId, entityId, values.label, values.condition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
      eventTriggerForm.reset();
    },
    onError: (error: Error) => toast.error(error.message || "Could not add event trigger"),
  });

  const deleteEventTrigger = useMutation({
    mutationFn: (eventTriggerId: string) =>
      api.deleteEventTrigger(accessToken!, projectId, entityId, eventTriggerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete event trigger"),
  });

  const addWorkflow = useMutation({
    mutationFn: (values: WorkflowCreateInput) =>
      api.createWorkflow(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add workflow"),
  });

  const deleteWorkflow = useMutation({
    mutationFn: (workflowId: string) =>
      api.deleteWorkflow(accessToken!, projectId, entityId, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete workflow"),
  });

  const addTrend = useMutation({
    mutationFn: (values: TrendCreateInput) =>
      api.createTrend(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add trend"),
  });

  const deleteTrend = useMutation({
    mutationFn: (trendId: string) => api.deleteTrend(accessToken!, projectId, entityId, trendId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete trend"),
  });

  const addErrorInjection = useMutation({
    mutationFn: (values: ErrorInjectionCreateInput) =>
      api.createErrorInjection(accessToken!, projectId, entityId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add error injection"),
  });

  const deleteErrorInjection = useMutation({
    mutationFn: (errorInjectionId: string) =>
      api.deleteErrorInjection(accessToken!, projectId, entityId, errorInjectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete error injection"),
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
    onError: (error: Error) => toast.error(error.message || "Could not add lookup"),
  });

  const deleteLookupAttachment = useMutation({
    mutationFn: (attachmentId: string) =>
      api.deleteLookupAttachment(accessToken!, projectId, entityId, attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete lookup"),
  });

  const restOutputsQuery = useQuery({
    queryKey: ["rest-outputs", projectId, entityId],
    queryFn: () => api.listRestOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [restOutputCount, setRestOutputCount] = useState(10);

  const addRestOutput = useMutation({
    mutationFn: () => api.createRestOutput(accessToken!, projectId, entityId, restOutputCount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rest-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not create REST output"),
  });

  const deleteRestOutput = useMutation({
    mutationFn: (outputId: string) => api.deleteRestOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rest-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete REST output"),
  });

  const streamsQuery = useQuery({
    queryKey: ["websocket-streams", projectId, entityId],
    queryFn: () => api.listWebSocketStreams(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [streamEventsPerSecond, setStreamEventsPerSecond] = useState(2);
  const [streamBatchSize, setStreamBatchSize] = useState(1);

  const addStream = useMutation({
    mutationFn: () =>
      api.createWebSocketStream(
        accessToken!,
        projectId,
        entityId,
        streamEventsPerSecond,
        streamBatchSize
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["websocket-streams", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not create stream"),
  });

  const deleteStream = useMutation({
    mutationFn: (streamId: string) =>
      api.deleteWebSocketStream(accessToken!, projectId, entityId, streamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["websocket-streams", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete stream"),
  });

  const downloadCsv = useMutation({
    mutationFn: () => api.generateCsv(accessToken!, projectId, entityId, count),
    onSuccess: (blob) => downloadBlob(blob, `${entity?.name ?? "export"}.csv`),
    onError: (error: Error) => toast.error(error.message || "CSV export failed"),
  });

  const downloadExcel = useMutation({
    mutationFn: () => api.generateExcel(accessToken!, projectId, entityId, count),
    onSuccess: (blob) => downloadBlob(blob, `${entity?.name ?? "export"}.xlsx`),
    onError: (error: Error) => toast.error(error.message || "Excel export failed"),
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
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div>
          <Link
            href={`/projects/${projectId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Back to project
          </Link>
        </div>

        <h1 className="text-2xl font-semibold tracking-tight">{entity?.name ?? "…"}</h1>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Fields</CardTitle>
            <AddFieldDialog onSubmit={(v) => addField.mutate(v)} isPending={addField.isPending} />
          </CardHeader>
          <CardContent>
            {entity?.fields.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No fields yet. Add one to start generating data.
              </p>
            )}
            {entity && entity.fields.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Constraints</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entity.fields.map((field) => (
                    <TableRow key={field.id}>
                      <TableCell className="font-medium">{field.name}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{field.field_type}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {[
                          field.required && "required",
                          field.unique && "unique",
                          !field.nullable && "not null",
                          field.min_value != null && `min ${field.min_value}`,
                          field.max_value != null && `max ${field.max_value}`,
                          field.regex && `regex ${field.regex}`,
                          field.preset && `preset ${field.preset.replaceAll("_", " ")}`,
                          field.enum_values &&
                            (field.enum_weights
                              ? field.enum_values
                                  .map((v, i) => `${v} (${field.enum_weights![i]})`)
                                  .join(" | ")
                              : field.enum_values.join(" | ")),
                          field.formula && `= ${field.formula}`,
                        ]
                          .filter(Boolean)
                          .join(", ") || "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteField.mutate(field.id)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rules</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              A rule is an expression a generated row must satisfy (e.g.{" "}
              <code className="font-mono">temperature &gt; 60</code>); rows that
              fail are discarded and regenerated.
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
              <p className="text-sm text-muted-foreground">No rules yet.</p>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Event triggers</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Unlike a rule, a matching trigger doesn&apos;t reject the row —
              it annotates it. Every trigger whose condition is true for a
              row appends its label to that row&apos;s{" "}
              <code className="font-mono">_triggered_events</code> list; no
              external notification is sent (yet).
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
              <p className="text-sm text-muted-foreground">No event triggers yet.</p>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Workflows</CardTitle>
            {entity && (
              <AddWorkflowDialog
                entity={entity}
                onSubmit={(v) => addWorkflow.mutate(v)}
                isPending={addWorkflow.isPending}
              />
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              A workflow turns a field into a simulated state machine: instead
              of a random value, each row gets a random walk from an initial
              state through the transitions you define, and the walk itself is
              included as <code className="font-mono">&lt;field&gt;_history</code>.
            </p>
            {entity?.workflows.length === 0 && (
              <p className="text-sm text-muted-foreground">No workflows yet.</p>
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
                      {workflow.transitions.map((t) => `${t.source}→${t.target}`).join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Trends</CardTitle>
            {entity && (
              <AddTrendDialog
                entity={entity}
                onSubmit={(v) => addTrend.mutate(v)}
                isPending={addTrend.isPending}
              />
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Makes a numeric field&apos;s value a function of its row&apos;s
              position within the batch (0, 1, 2, …) instead of an independent
              random draw — e.g. a linear trend rises steadily across a
              generated batch. Position resets to 0 on every generate call.
            </p>
            {entity?.trends.length === 0 && (
              <p className="text-sm text-muted-foreground">No trends yet.</p>
            )}
            {entity && entity.trends.length > 0 && (
              <ul className="flex flex-col gap-2">
                {entity.trends.map((trend) => (
                  <li
                    key={trend.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span>
                      <span className="font-medium">{fieldNameById.get(trend.field_id)}</span>
                      <span className="ml-2 text-muted-foreground">
                        {trend.trend_type.replaceAll("_", " ")} (
                        {Object.entries(trend.params)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(", ")}
                        )
                      </span>
                    </span>
                    <Button variant="ghost" size="sm" onClick={() => deleteTrend.mutate(trend.id)}>
                      Delete
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Error injection</CardTitle>
            {entity && (
              <AddErrorInjectionDialog
                entity={entity}
                onSubmit={(v) => addErrorInjection.mutate(v)}
                isPending={addErrorInjection.isPending}
              />
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Deliberately corrupts a field&apos;s value on some fraction of
              generated rows — nulls, empty strings, duplicates, truncated
              text, wrong types, or out-of-range numbers — to simulate the bad
              data a real pipeline has to handle. A rule constraining the same
              field evaluates rows after corruption, so it can end up
              filtering the corrupted rows back out.
            </p>
            {entity?.error_injections.length === 0 && (
              <p className="text-sm text-muted-foreground">No error injections yet.</p>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Lookups</CardTitle>
            {entity && (
              <AddLookupAttachmentDialog
                entity={entity}
                lookupTables={lookupTables}
                onSubmit={(v) => addLookupAttachment.mutate(v)}
                isPending={addLookupAttachment.isPending}
              />
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Draws a field&apos;s value from a column of a project-level
              lookup table instead of randomizing it — upload reference data
              on the project page first. Unlike a relationship, this works
              from this entity&apos;s own Generate button too, not just
              project-wide generation.
            </p>
            {lookupTables.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No lookup tables in this project yet — upload one from the
                project page.
              </p>
            )}
            {entity?.lookup_attachments.length === 0 && lookupTables.length > 0 && (
              <p className="text-sm text-muted-foreground">No lookups attached yet.</p>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">REST output</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              A public, unauthenticated URL that returns freshly generated rows
              for this entity on every request — point a frontend&apos;s{" "}
              <code className="font-mono">fetch()</code> straight at it during
              development. Anyone with the link can use it, the same as a
              webhook URL.
            </p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={5000}
                value={restOutputCount}
                onChange={(e) => setRestOutputCount(Number(e.target.value))}
                className="w-32"
              />
              <Button
                onClick={() => addRestOutput.mutate()}
                disabled={addRestOutput.isPending || !entity?.fields.length}
              >
                {addRestOutput.isPending ? "Creating…" : "Create endpoint"}
              </Button>
            </div>
            {restOutputsQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No REST outputs yet.</p>
            )}
            {restOutputsQuery.data && restOutputsQuery.data.length > 0 && (
              <ul className="flex flex-col gap-2">
                {restOutputsQuery.data.map((output) => {
                  const url = `${API_URL}/public/rest/${output.token}`;
                  return (
                    <li
                      key={output.id}
                      className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                    >
                      <code className="truncate font-mono">{url}</code>
                      <div className="flex shrink-0 gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            navigator.clipboard.writeText(url);
                            toast.success("Copied");
                          }}
                        >
                          Copy
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteRestOutput.mutate(output.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Live stream (WebSocket)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              A public, unauthenticated WebSocket that pushes a fresh batch
              every tick for as long as a client stays connected — no auth,
              no polling. Disconnecting stops production; there&apos;s nothing
              running in the background otherwise.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 text-sm">
                <span className="text-muted-foreground">events/sec</span>
                <Input
                  type="number"
                  min={0.1}
                  max={50}
                  step={0.1}
                  value={streamEventsPerSecond}
                  onChange={(e) => setStreamEventsPerSecond(Number(e.target.value))}
                  className="w-20"
                />
              </div>
              <div className="flex items-center gap-1 text-sm">
                <span className="text-muted-foreground">rows/message</span>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={streamBatchSize}
                  onChange={(e) => setStreamBatchSize(Number(e.target.value))}
                  className="w-20"
                />
              </div>
              <Button
                onClick={() => addStream.mutate()}
                disabled={addStream.isPending || !entity?.fields.length}
              >
                {addStream.isPending ? "Creating…" : "Create stream"}
              </Button>
            </div>
            {streamsQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No streams yet.</p>
            )}
            {streamsQuery.data && streamsQuery.data.length > 0 && (
              <ul className="flex flex-col gap-3">
                {streamsQuery.data.map((stream) => {
                  const wsUrl = `${WS_URL}/public/stream/${stream.token}`;
                  return (
                    <li key={stream.id} className="flex flex-col gap-2">
                      <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                        <code className="truncate font-mono">{wsUrl}</code>
                        <div className="flex shrink-0 gap-2">
                          <span className="text-muted-foreground">
                            {stream.events_per_second}/s × {stream.batch_size}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteStream.mutate(stream.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                      <StreamPreview wsUrl={wsUrl} />
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Generate</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
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
              <div className="overflow-x-auto rounded-md border">
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
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
