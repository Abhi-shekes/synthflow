"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelEmpty, PanelHeader, PanelTitle } from "@/components/ui/panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/**
 * Build a new project from data already sitting in this project's bucket or
 * database — the same places generation writes to.
 *
 * Reading a database table keeps its real column types, so dates stay dates
 * rather than becoming strings the way a CSV round-trip would.
 */
export function LearnSourcePanel({ projectId }: { projectId: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [kind, setKind] = useState<"object" | "table">("object");
  const [targetId, setTargetId] = useState("");
  const [names, setNames] = useState("");

  const storageQuery = useQuery({
    queryKey: ["storage-targets", projectId],
    queryFn: () => api.listStorageTargets(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const connectionsQuery = useQuery({
    queryKey: ["database-connections", projectId],
    queryFn: () => api.listDatabaseConnections(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const objectsQuery = useQuery({
    queryKey: ["source-objects", projectId, targetId],
    queryFn: () => api.listSourceObjects(accessToken!, projectId, targetId),
    enabled: !!accessToken && kind === "object" && !!targetId,
  });

  const learn = useMutation({
    // Profiling and applying are both inside the mutation rather than chained
    // through onSuccess: failing to create the project is just as worth
    // reporting as failing to read the source, and an error thrown from
    // onSuccess never reaches onError.
    mutationFn: async () => {
      const wanted = names
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      if (wanted.length === 0) throw new Error("Name at least one object or table");
      const profiled = await api.profileFromSource(accessToken!, {
        project_id: projectId,
        ...(kind === "object"
          ? { storage_target_id: targetId, object_keys: wanted }
          : { connection_id: targetId, tables: wanted }),
      });
      return api.importProject(accessToken!, profiled.template);
    },
    onSuccess: (project) => {
      toast.success(`Learned "${project.name}" from that source`);
      setNames("");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not learn from that source"),
  });

  const options =
    kind === "object"
      ? (storageQuery.data ?? []).map((t) => ({ id: t.id, label: t.name }))
      : (connectionsQuery.data ?? []).map((c) => ({ id: c.id, label: c.name }));

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Learn from a connected source</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-col gap-3">
        <p className="text-xs leading-relaxed text-ink-dim">
          Profiles real data and turns it into an ordinary editable project — fitted
          distributions, observed category frequencies, per-column null rates and
          correlations. Personal data is detected and replaced with synthetic generators
          during profiling, so no value from the source reaches the new project.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={kind}
            onValueChange={(v) => {
              setKind((v ?? "object") as "object" | "table");
              // A target id only means something within its own kind.
              setTargetId("");
            }}
          >
            <SelectTrigger className="h-8 w-40 text-xs">
              <SelectValue>
                {(v: string) => (v === "table" ? "Database table" : "Object storage")}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="object">Object storage</SelectItem>
              <SelectItem value="table">Database table</SelectItem>
            </SelectContent>
          </Select>

          <Select value={targetId} onValueChange={(v) => setTargetId(v ?? "")}>
            <SelectTrigger className="h-8 w-48 text-xs">
              <SelectValue placeholder={kind === "object" ? "Storage target" : "Connection"} />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {options.length === 0 ? (
          <PanelEmpty>
            {kind === "object"
              ? "No storage targets yet — add one above."
              : "No database connections yet — add one above."}
          </PanelEmpty>
        ) : (
          <>
            <Textarea
              className="min-h-20 font-mono text-xs"
              placeholder={
                kind === "object" ? "exports/customers.csv\nexports/orders.csv" : "customers\norders"
              }
              value={names}
              onChange={(event) => setNames(event.target.value)}
            />
            {kind === "object" && (objectsQuery.data ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {(objectsQuery.data ?? []).slice(0, 12).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setNames((prev) => (prev ? `${prev}\n${key}` : key))}
                    className="rounded border border-line-soft bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-ink-dim hover:border-ink-faint"
                  >
                    {key}
                  </button>
                ))}
              </div>
            )}
            <Button
              size="sm"
              className="self-start"
              disabled={!targetId || learn.isPending}
              onClick={() => learn.mutate()}
            >
              {learn.isPending ? "Profiling…" : "Learn from this"}
            </Button>
          </>
        )}
      </PanelBody>
    </Panel>
  );
}
