"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddRelationshipDialog } from "@/components/add-relationship-dialog";
import { AppShell } from "@/components/app-shell";
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
import type { RelationshipCreateInput } from "@/lib/types";

interface FormValues {
  name: string;
}

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
