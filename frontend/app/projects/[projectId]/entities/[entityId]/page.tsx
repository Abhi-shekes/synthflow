"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddFieldDialog } from "@/components/add-field-dialog";
import { AddWorkflowDialog } from "@/components/add-workflow-dialog";
import { AppShell } from "@/components/app-shell";
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
import type { FieldCreateInput, WorkflowCreateInput } from "@/lib/types";

interface RuleFormValues {
  condition: string;
}

export default function EntityDetailPage() {
  const accessToken = useRequireAuth();
  const { projectId, entityId } = useParams<{ projectId: string; entityId: string }>();
  const queryClient = useQueryClient();
  const [count, setCount] = useState(10);
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);
  const ruleForm = useForm<RuleFormValues>();

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
                          field.enum_values && field.enum_values.join(" | "),
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
