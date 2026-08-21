"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddDatabaseConnectionDialog } from "@/components/add-database-connection-dialog";
import { AddLookupTableDialog } from "@/components/add-lookup-table-dialog";
import { AddRelationshipDialog } from "@/components/add-relationship-dialog";
import { AddTimelineReplayDialog } from "@/components/add-timeline-replay-dialog";
import { AppShell } from "@/components/app-shell";
import { StreamPreview } from "@/components/stream-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  DatabaseConnectionCreateInput,
  RelationshipCreateInput,
  TimelineReplayCreateInput,
} from "@/lib/types";

interface FormValues {
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const WS_URL = API_URL.replace(/^http/, "ws");

export default function ProjectDetailPage() {
  const accessToken = useRequireAuth();
  const router = useRouter();
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset } = useForm<FormValues>();

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const entitiesQuery = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => api.listEntities(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const relationshipsQuery = useQuery({
    queryKey: ["relationships", projectId],
    queryFn: () => api.listRelationships(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const connectionsQuery = useQuery({
    queryKey: ["database-connections", projectId],
    queryFn: () => api.listDatabaseConnections(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const lookupTablesQuery = useQuery({
    queryKey: ["lookup-tables", projectId],
    queryFn: () => api.listLookupTables(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const createEntity = useMutation({
    mutationFn: (values: FormValues) => api.createEntity(accessToken!, projectId, values.name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
      reset();
    },
    onError: (error: Error) => toast.error(error.message || "Could not create entity"),
  });

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(accessToken!, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push("/projects");
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete project"),
  });

  const createRelationship = useMutation({
    mutationFn: (values: RelationshipCreateInput) =>
      api.createRelationship(accessToken!, projectId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relationships", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not create relationship"),
  });

  const deleteRelationship = useMutation({
    mutationFn: (relationshipId: string) =>
      api.deleteRelationship(accessToken!, projectId, relationshipId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relationships", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete relationship"),
  });

  const createConnection = useMutation({
    mutationFn: (values: DatabaseConnectionCreateInput) =>
      api.createDatabaseConnection(accessToken!, projectId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["database-connections", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add connection"),
  });

  const deleteConnection = useMutation({
    mutationFn: (connectionId: string) =>
      api.deleteDatabaseConnection(accessToken!, projectId, connectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["database-connections", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete connection"),
  });

  const testConnection = useMutation({
    mutationFn: (connectionId: string) =>
      api.testDatabaseConnection(accessToken!, projectId, connectionId),
    onSuccess: (result) => {
      if (result.ok) toast.success(result.detail);
      else toast.error(result.detail);
    },
    onError: (error: Error) => toast.error(error.message || "Test failed"),
  });

  const createLookupTable = useMutation({
    mutationFn: (values: { name: string; file: File }) =>
      api.createLookupTable(accessToken!, projectId, values.name, values.file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lookup-tables", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not upload lookup table"),
  });

  const deleteLookupTable = useMutation({
    mutationFn: (lookupTableId: string) =>
      api.deleteLookupTable(accessToken!, projectId, lookupTableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lookup-tables", projectId] });
      // A deleted lookup table cascades to any entity's lookup attachment —
      // refresh entities so those cards reflect that immediately.
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete lookup table"),
  });

  const timelineReplaysQuery = useQuery({
    queryKey: ["timeline-replays", projectId],
    queryFn: () => api.listTimelineReplays(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const createTimelineReplay = useMutation({
    mutationFn: (values: TimelineReplayCreateInput) =>
      api.createTimelineReplay(accessToken!, projectId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["timeline-replays", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not add timeline replay"),
  });

  const deleteTimelineReplay = useMutation({
    mutationFn: (replayId: string) =>
      api.deleteTimelineReplay(accessToken!, projectId, replayId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["timeline-replays", projectId] });
    },
    onError: (error: Error) => toast.error(error.message || "Could not delete timeline replay"),
  });

  const [pushConnectionId, setPushConnectionId] = useState("");
  const [pushEntityId, setPushEntityId] = useState("");
  const [pushCount, setPushCount] = useState(10);

  const pushToDatabase = useMutation({
    mutationFn: () =>
      api.pushToDatabaseConnection(
        accessToken!,
        projectId,
        pushConnectionId,
        pushEntityId,
        pushCount
      ),
    onSuccess: (result) =>
      toast.success(`Wrote ${result.rows_written} row(s) to '${result.table}'`),
    onError: (error: Error) => toast.error(error.message || "Push failed"),
  });

  const [generateCount, setGenerateCount] = useState(10);
  const [generated, setGenerated] = useState<Record<string, Record<string, unknown>[]> | null>(
    null
  );

  const generateAll = useMutation({
    mutationFn: () => api.generateProject(accessToken!, projectId, generateCount),
    onSuccess: (data) => setGenerated(data),
    onError: (error: Error) => toast.error(error.message || "Generation failed"),
  });

  const downloadCsvZip = useMutation({
    mutationFn: () => api.generateProjectCsvZip(accessToken!, projectId, generateCount),
    onSuccess: (blob) => downloadBlob(blob, `${projectQuery.data?.name ?? "project"}.zip`),
    onError: (error: Error) => toast.error(error.message || "CSV export failed"),
  });

  const downloadExcel = useMutation({
    mutationFn: () => api.generateProjectExcel(accessToken!, projectId, generateCount),
    onSuccess: (blob) => downloadBlob(blob, `${projectQuery.data?.name ?? "project"}.xlsx`),
    onError: (error: Error) => toast.error(error.message || "Excel export failed"),
  });

  if (!accessToken) return null;

  const entities = entitiesQuery.data ?? [];
  const entityById = new Map(entities.map((e) => [e.id, e]));
  const lookupTables = lookupTablesQuery.data ?? [];
  const lookupTableById = new Map(lookupTables.map((t) => [t.id, t]));
  const fieldLabel = (entityId: string, fieldId: string) => {
    const field = entityById.get(entityId)?.fields.find((f) => f.id === fieldId);
    return field?.name ?? "?";
  };

  return (
    <AppShell>
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <Link href="/projects" className="text-sm text-muted-foreground hover:underline">
            ← Projects
          </Link>
        </div>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {projectQuery.data?.name ?? "…"}
            </h1>
            {projectQuery.data?.description && (
              <p className="mt-1 text-sm text-muted-foreground">
                {projectQuery.data.description}
              </p>
            )}
          </div>
          <Button
            variant="destructive"
            size="sm"
            disabled={deleteProject.isPending}
            onClick={() => {
              if (confirm("Delete this project and all its entities?")) {
                deleteProject.mutate();
              }
            }}
          >
            Delete project
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add an entity</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="flex gap-2"
              onSubmit={handleSubmit((values) => createEntity.mutate(values))}
            >
              <Input placeholder="e.g. Customer" {...register("name", { required: true })} />
              <Button type="submit" disabled={createEntity.isPending}>
                Add
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">Entities</h2>
          {entitiesQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No entities yet. Add one above to start defining fields.
            </p>
          )}
          {entitiesQuery.data?.map((entity) => (
            <Link key={entity.id} href={`/projects/${projectId}/entities/${entity.id}`}>
              <Card className="transition-colors hover:border-foreground/30">
                <CardContent className="flex items-center justify-between py-4">
                  <span className="font-medium">{entity.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {entity.fields.length} field{entity.fields.length === 1 ? "" : "s"}
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Relationships</CardTitle>
            <AddRelationshipDialog
              entities={entities}
              onSubmit={(v) => createRelationship.mutate(v)}
              isPending={createRelationship.isPending}
            />
          </CardHeader>
          <CardContent>
            {entities.length < 2 && (
              <p className="text-sm text-muted-foreground">
                Add at least two entities (each with fields) to connect them.
              </p>
            )}
            {relationshipsQuery.data?.length === 0 && entities.length >= 2 && (
              <p className="text-sm text-muted-foreground">
                No relationships yet. A relationship makes a foreign-key field on
                one entity draw its generated values from another entity instead
                of random data.
              </p>
            )}
            {relationshipsQuery.data && relationshipsQuery.data.length > 0 && (
              <ul className="flex flex-col gap-2">
                {relationshipsQuery.data.map((rel) => (
                  <li
                    key={rel.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span>
                      <span className="font-medium">
                        {entityById.get(rel.source_entity_id)?.name}.
                        {fieldLabel(rel.source_entity_id, rel.source_field_id)}
                      </span>
                      {" → "}
                      <span className="font-medium">
                        {entityById.get(rel.target_entity_id)?.name}.
                        {fieldLabel(rel.target_entity_id, rel.target_field_id)}
                      </span>
                      <span className="ml-2 text-muted-foreground">
                        ({rel.relationship_type.replaceAll("_", "-")})
                      </span>
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteRelationship.mutate(rel.id)}
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
            <CardTitle className="text-base">Database connections</CardTitle>
            <AddDatabaseConnectionDialog
              onSubmit={(v) => createConnection.mutate(v)}
              isPending={createConnection.isPending}
            />
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Write generated rows straight into an external database instead
              of just downloading them. PostgreSQL only for now.
            </p>
            {connectionsQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No connections yet.</p>
            )}
            {connectionsQuery.data && connectionsQuery.data.length > 0 && (
              <ul className="flex flex-col gap-2">
                {connectionsQuery.data.map((conn) => (
                  <li
                    key={conn.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span>
                      <span className="font-medium">{conn.name}</span>{" "}
                      <Badge variant="secondary">{conn.dialect}</Badge>{" "}
                      <span className="text-muted-foreground">
                        {conn.host}:{conn.port}/{conn.database}
                      </span>
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => testConnection.mutate(conn.id)}
                        disabled={testConnection.isPending}
                      >
                        Test
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteConnection.mutate(conn.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {connectionsQuery.data && connectionsQuery.data.length > 0 && entities.length > 0 && (
              <div className="flex flex-col gap-2 rounded-md border p-3">
                <p className="text-sm font-medium">Push data to a connection</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Select value={pushConnectionId} onValueChange={(v) => setPushConnectionId(v ?? "")}>
                    <SelectTrigger className="w-48">
                      <SelectValue>
                        {(v: string) =>
                          v ? connectionsQuery.data?.find((c) => c.id === v)?.name : "Connection"
                        }
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {connectionsQuery.data.map((conn) => (
                        <SelectItem key={conn.id} value={conn.id}>
                          {conn.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={pushEntityId} onValueChange={(v) => setPushEntityId(v ?? "")}>
                    <SelectTrigger className="w-48">
                      <SelectValue>
                        {(v: string) => (v ? entities.find((e) => e.id === v)?.name : "Entity")}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {entities.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    min={1}
                    max={5000}
                    value={pushCount}
                    onChange={(e) => setPushCount(Number(e.target.value))}
                    className="w-24"
                  />
                  <Button
                    onClick={() => pushToDatabase.mutate()}
                    disabled={pushToDatabase.isPending || !pushConnectionId || !pushEntityId}
                  >
                    {pushToDatabase.isPending ? "Pushing…" : "Push"}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Lookup tables</CardTitle>
            <AddLookupTableDialog
              onSubmit={(v) => createLookupTable.mutate(v)}
              isPending={createLookupTable.isPending}
            />
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Reference data uploaded once (CSV, Excel, or JSON) that any
              field in this project can draw real values from — see a
              field&apos;s <span className="font-mono">Add lookup</span> option
              on its entity page.
            </p>
            {lookupTablesQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No lookup tables yet.</p>
            )}
            {lookupTablesQuery.data && lookupTablesQuery.data.length > 0 && (
              <ul className="flex flex-col gap-2">
                {lookupTablesQuery.data.map((table) => (
                  <li
                    key={table.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span>
                      <span className="font-medium">{table.name}</span>{" "}
                      <span className="text-muted-foreground">
                        {table.row_count} row{table.row_count === 1 ? "" : "s"} ·{" "}
                        {table.columns.join(", ")}
                      </span>
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteLookupTable.mutate(table.id)}
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
            <CardTitle className="text-base">Timeline replays</CardTitle>
            <AddTimelineReplayDialog
              lookupTables={lookupTables}
              onSubmit={(v) => createTimelineReplay.mutate(v)}
              isPending={createTimelineReplay.isPending}
            />
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Replays an uploaded lookup table&apos;s rows over a public
              WebSocket in their original timestamp order, at N&times; real
              time, looping once it reaches the end — a historical dataset
              turned into a live feed for testing stream consumers against
              realistic timing, not just realistic content.
            </p>
            {timelineReplaysQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No timeline replays yet.</p>
            )}
            {timelineReplaysQuery.data && timelineReplaysQuery.data.length > 0 && (
              <ul className="flex flex-col gap-3">
                {timelineReplaysQuery.data.map((replay) => {
                  const wsUrl = `${WS_URL}/public/replay/${replay.token}`;
                  return (
                    <li key={replay.id} className="flex flex-col gap-2">
                      <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                        <span className="truncate">
                          <span className="font-medium">
                            {lookupTableById.get(replay.lookup_table_id)?.name ?? "?"}
                          </span>
                          <span className="ml-2 text-muted-foreground">
                            {replay.timestamp_column} · {replay.speed_multiplier}&times;
                          </span>
                        </span>
                        <div className="flex shrink-0 gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard.writeText(wsUrl);
                              toast.success("Copied");
                            }}
                          >
                            Copy URL
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteTimelineReplay.mutate(replay.id)}
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
            <CardTitle className="text-base">Generate all entities</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Generates every entity in this project at once. Entities involved in
              a relationship draw their foreign-key values from the referenced
              entity&apos;s generated rows.
            </p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={5000}
                value={generateCount}
                onChange={(e) => setGenerateCount(Number(e.target.value))}
                className="w-32"
              />
              <Button
                onClick={() => generateAll.mutate()}
                disabled={generateAll.isPending || entities.length === 0}
              >
                {generateAll.isPending ? "Generating…" : "Generate all"}
              </Button>
              <Button
                variant="outline"
                onClick={() => downloadCsvZip.mutate()}
                disabled={downloadCsvZip.isPending || entities.length === 0}
              >
                {downloadCsvZip.isPending ? "Preparing…" : "Download CSV (zip)"}
              </Button>
              <Button
                variant="outline"
                onClick={() => downloadExcel.mutate()}
                disabled={downloadExcel.isPending || entities.length === 0}
              >
                {downloadExcel.isPending ? "Preparing…" : "Download Excel"}
              </Button>
            </div>

            {generated &&
              Object.entries(generated).map(([entityName, rows]) => (
                <div key={entityName} className="flex flex-col gap-2">
                  <h3 className="text-sm font-medium">
                    {entityName} ({rows.length} row{rows.length === 1 ? "" : "s"})
                  </h3>
                  {rows.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No fields to generate.</p>
                  ) : (
                    <div className="overflow-x-auto rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            {Object.keys(rows[0]).map((col) => (
                              <TableHead key={col}>{col}</TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {rows.map((row, i) => (
                            <TableRow key={i}>
                              {Object.keys(rows[0]).map((col) => (
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
                </div>
              ))}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
