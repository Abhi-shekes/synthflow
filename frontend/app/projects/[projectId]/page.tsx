"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Download, LayoutGrid, Trash2, Waypoints } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AddRelationshipDialog } from "@/components/add-relationship-dialog";
import { AppShell } from "@/components/app-shell";
import { SystemMap, SystemMapList, type MapSource } from "@/components/map/system-map";
import { SectionHeader } from "@/components/section-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Panel,
  PanelBody,
  PanelEmpty,
  PanelHeader,
  PanelTitle,
} from "@/components/ui/panel";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { markChecklistStep } from "@/lib/checklist";
import { downloadBlob } from "@/lib/download";
import { fieldFill, OUTPUT_COLOR, SECTION_COLOR } from "@/lib/field-visual";
import { useRequireAuth, useViewMode } from "@/lib/hooks";
import { useMetricsStream } from "@/lib/use-metrics-stream";
import { cn } from "@/lib/utils";
import type { RelationshipCreateInput } from "@/lib/types";

interface FormValues {
  name: string;
}

/**
 * The project as a pipeline, on one canvas.
 *
 * What used to be here — ten stacked cards covering entities, relationships,
 * storage, connections, lookup tables, replays, jobs, versions, activity and
 * sharing — is now split by what you came to do: designing happens here, running
 * happens on Data, and history happens on Governance.
 */
export default function ProjectMapPage() {
  const accessToken = useRequireAuth();
  const router = useRouter();
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset } = useForm<FormValues>();
  const [generateCount, setGenerateCount] = useState(100);

  // Guided mode defaults to the list view — a canvas with z-plane parallax
  // and level-of-detail-on-zoom is a real "wow" once you already understand
  // the pipeline shape, and one more thing to parse before then. `null`
  // means "follow the mode"; once someone flips the toggle by hand it's
  // remembered as an explicit choice for the rest of this visit.
  const mode = useViewMode();
  const [canvasOverride, setCanvasOverride] = useState<boolean | null>(null);
  const showCanvas = canvasOverride ?? mode === "advanced";

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

  const outputsQuery = useQuery({
    queryKey: ["outputs", projectId],
    queryFn: () => api.listOutputs(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const connectionsQuery = useQuery({
    queryKey: ["database-connections", projectId],
    queryFn: () => api.listDatabaseConnections(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const storageQuery = useQuery({
    queryKey: ["storage-targets", projectId],
    queryFn: () => api.listStorageTargets(accessToken!, projectId),
    enabled: !!accessToken,
  });

  // The map animates its edges only while the engine is actually producing.
  // A pipeline drawn as permanently flowing tells you nothing; one that moves
  // when rows move tells you something true.
  const { history } = useMetricsStream(accessToken, 4000);
  const flowing = (history[history.length - 1]?.totalRowsPerSecond ?? 0) > 0;
  const activity = flowing
    ? Object.fromEntries(entitiesQuery.data?.map((entity) => [entity.id, 1]) ?? [])
    : undefined;

  const entities = entitiesQuery.data ?? [];
  const relationships = relationshipsQuery.data ?? [];

  const createEntity = useMutation({
    mutationFn: (values: FormValues) => api.createEntity(accessToken!, projectId, values.name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
      markChecklistStep("entity");
      reset();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create entity"),
  });

  const createRelationship = useMutation({
    mutationFn: (values: RelationshipCreateInput) =>
      api.createRelationship(accessToken!, projectId, values),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["relationships", projectId] }),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create relationship"),
  });

  const deleteRelationship = useMutation({
    mutationFn: (id: string) => api.deleteRelationship(accessToken!, projectId, id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["relationships", projectId] }),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete relationship"),
  });

  const exportProject = useMutation({
    mutationFn: () => api.exportProject(accessToken!, projectId),
    onSuccess: (template) => {
      const blob = new Blob([JSON.stringify(template, null, 2)], { type: "application/json" });
      downloadBlob(blob, `${template.name || "project"}.synthflow.json`);
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not export project"),
  });

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(accessToken!, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push("/projects");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete project"),
  });

  const downloadCsvZip = useMutation({
    mutationFn: () => api.generateProjectCsvZip(accessToken!, projectId, generateCount),
    onSuccess: (blob) => downloadBlob(blob, "project.zip"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not export"),
  });

  const downloadExcel = useMutation({
    mutationFn: () => api.generateProjectExcel(accessToken!, projectId, generateCount),
    onSuccess: (blob) => downloadBlob(blob, "project.xlsx"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not export"),
  });

  // The map's left column: everything this project can learn from or read.
  const sources: MapSource[] = [
    ...(storageQuery.data ?? []).map((target) => ({
      id: target.id,
      label: target.name,
      detail: `s3://${target.bucket}`,
      color: OUTPUT_COLOR.storage,
    })),
    ...(connectionsQuery.data ?? []).map((connection) => ({
      id: connection.id,
      label: connection.name,
      detail: `${connection.dialect} · ${connection.database}`,
      color: OUTPUT_COLOR.database,
    })),
  ];

  const fieldCount = entities.reduce((sum, entity) => sum + entity.fields.length, 0);

  return (
    <AppShell>
      <div className="flex w-full flex-col gap-6">
        <div data-tour="system-map-header">
        <SectionHeader
          icon={Boxes}
          color={SECTION_COLOR.map}
          eyebrow="System map"
          title={projectQuery.data?.name ?? "…"}
          description={
            <>
              {projectQuery.data?.description}
              <span className="mt-1 block font-mono text-xs text-ink-faint">
                {entities.length} entities · {fieldCount} fields · {relationships.length}{" "}
                relationships · {(outputsQuery.data ?? []).length} outputs
              </span>
            </>
          }
          action={
          <div className="flex items-center gap-2">
            <div
              role="group"
              aria-label="Map or list view"
              className="hidden items-center gap-0.5 rounded-lg border border-line bg-surface-2 p-0.5 md:flex"
            >
              <button
                type="button"
                title="List view"
                aria-pressed={!showCanvas}
                onClick={() => setCanvasOverride(false)}
                className={cn(
                  "flex size-7 items-center justify-center rounded-md transition-colors",
                  "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  !showCanvas ? "bg-surface text-ink shadow-sm" : "text-ink-faint hover:text-ink-dim"
                )}
              >
                <LayoutGrid className="size-3.5" />
              </button>
              <button
                type="button"
                title="Map view"
                aria-pressed={showCanvas}
                onClick={() => setCanvasOverride(true)}
                className={cn(
                  "flex size-7 items-center justify-center rounded-md transition-colors",
                  "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  showCanvas ? "bg-surface text-ink shadow-sm" : "text-ink-faint hover:text-ink-dim"
                )}
              >
                <Waypoints className="size-3.5" />
              </button>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportProject.mutate()}
              disabled={exportProject.isPending}
            >
              <Download />
              Export
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Delete project"
              onClick={() => {
                if (
                  window.confirm(
                    `Delete "${projectQuery.data?.name}" and everything in it? This cannot be undone.`
                  )
                ) {
                  deleteProject.mutate();
                }
              }}
            >
              <Trash2 />
            </Button>
          </div>
          }
        />
        </div>

        {/* The canvas from md up, when selected; a list otherwise — always a
            list below md, since a canvas on a phone is not a canvas. */}
        {showCanvas && (
          <div className="hidden md:block">
            <SystemMap
              projectId={projectId}
              entities={entities}
              relationships={relationships}
              outputs={outputsQuery.data ?? []}
              sources={sources}
              activity={activity}
            />
          </div>
        )}
        <div className={cn(showCanvas && "md:hidden")}>
          {entities.length === 0 ? (
            <PanelEmpty>No entities yet.</PanelEmpty>
          ) : (
            <SystemMapList projectId={projectId} entities={entities} />
          )}
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Panel data-tour="add-entity" tone="marked" accent={SECTION_COLOR.map}>
            <PanelHeader>
              <PanelTitle>Add an entity</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <form
                className="flex items-center gap-2"
                onSubmit={handleSubmit((values) => createEntity.mutate(values))}
              >
                <Input
                  placeholder="Customer"
                  className="h-8"
                  {...register("name", { required: true })}
                />
                <Button size="sm" type="submit" disabled={createEntity.isPending}>
                  {createEntity.isPending ? "Adding…" : "Add"}
                </Button>
              </form>
              <p className="mt-2 text-xs leading-relaxed text-ink-dim">
                An entity is one table of generated rows. It appears on the map immediately,
                and its bands fill in as you add fields.
              </p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Relationships</PanelTitle>
              <AddRelationshipDialog
                entities={entities}
                onSubmit={(v) => createRelationship.mutate(v)}
                isPending={createRelationship.isPending}
              />
            </PanelHeader>
            <PanelBody className="flex flex-col gap-2">
              {relationships.length === 0 ? (
                <PanelEmpty>
                  No relationships yet. Link two entities and a child&apos;s foreign keys start
                  drawing from the parent&apos;s generated rows.
                </PanelEmpty>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {relationships.map((relationship) => {
                    const source = entities.find(
                      (e) => e.id === relationship.source_entity_id
                    );
                    const target = entities.find(
                      (e) => e.id === relationship.target_entity_id
                    );
                    const field = source?.fields.find(
                      (f) => f.id === relationship.source_field_id
                    );
                    return (
                      <li
                        key={relationship.id}
                        className="flex flex-wrap items-center gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-2"
                      >
                        {field && (
                          <span
                            aria-hidden
                            className="h-3.5 w-1 shrink-0 rounded-full"
                            style={{ background: fieldFill(field.field_type, field.preset) }}
                          />
                        )}
                        <span className="font-mono text-xs">
                          {source?.name ?? "?"} → {target?.name ?? "?"}
                        </span>
                        <span className="font-mono text-xs text-ink-faint">
                          {relationship.relationship_type.replaceAll("_", " ")}
                        </span>
                        <Button
                          size="xs"
                          variant="ghost"
                          className="ml-auto"
                          onClick={() => deleteRelationship.mutate(relationship.id)}
                        >
                          Delete
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </PanelBody>
          </Panel>
        </div>

        <Panel>
          <PanelHeader>
            <PanelTitle>Export the whole project</PanelTitle>
          </PanelHeader>
          <PanelBody className="flex flex-col gap-3">
            <p className="text-xs leading-relaxed text-ink-dim">
              Generates every entity at once and downloads the result. Entities in a
              relationship draw their foreign keys from the referenced entity&apos;s rows, so
              the files stay consistent with each other. For anything large, or on a schedule,
              queue a job on the Data page instead — it streams and survives a restart.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                min={1}
                max={5000}
                className="h-8 w-28"
                value={generateCount}
                onChange={(event) => setGenerateCount(Number(event.target.value))}
              />
              <Button
                size="sm"
                variant="outline"
                onClick={() => downloadCsvZip.mutate()}
                disabled={downloadCsvZip.isPending || entities.length === 0}
              >
                {downloadCsvZip.isPending ? "Preparing…" : "CSV (zip)"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => downloadExcel.mutate()}
                disabled={downloadExcel.isPending || entities.length === 0}
              >
                {downloadExcel.isPending ? "Preparing…" : "Excel"}
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </AppShell>
  );
}
