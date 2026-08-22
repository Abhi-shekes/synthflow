"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { VersionDiff } from "@/lib/types";

/**
 * Snapshots of the project's design, with a diff and a rollback.
 *
 * Snapshots are explicit: recording one on every mutation sounds thorough
 * and produces a history nobody can read — fifty entries for an afternoon's
 * editing, forty-nine of them a field half-renamed.
 */
export function VersionHistoryCard({ projectId }: { projectId: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [openDiff, setOpenDiff] = useState<number | null>(null);

  const versions = useQuery({
    queryKey: ["project-versions", projectId],
    queryFn: () => api.listProjectVersions(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project-versions", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["relationships", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
      // Every open diff is against a project that just changed underneath
      // it, so leaving them cached shows a comparison to a state that no
      // longer exists — which is worse than showing none.
      queryClient.invalidateQueries({ queryKey: ["project-version-diff", projectId] }),
    ]);

  const snapshot = useMutation({
    mutationFn: () => api.createProjectVersion(accessToken!, projectId, label.trim() || null),
    onSuccess: (version) => {
      toast.success(`Saved as v${version.version}`);
      setLabel("");
      return refresh();
    },
    onError: (error: Error) => toast.error(error.message || "Could not snapshot"),
  });

  const rollback = useMutation({
    mutationFn: async (version: number) => {
      try {
        return await api.rollbackProject(accessToken!, projectId, version);
      } catch (error) {
        // The server refuses with 409 when a rollback would delete stored
        // records. Asking here rather than sending `discard` by default:
        // losing a generated population as a side effect of reverting a
        // schema is not something to find out about afterwards.
        const message = error instanceof Error ? error.message : "";
        if (!message.includes("stored records")) throw error;
        if (!window.confirm(`${message}\n\nDelete those records and roll back anyway?`)) {
          throw new Error("Rollback cancelled");
        }
        return api.rollbackProject(accessToken!, projectId, version, true);
      }
    },
    onSuccess: (result) => {
      toast.success(
        `Rolled back to v${result.restored_from} — the previous state is saved as ` +
          `v${result.backup_version} if you want it back`
      );
      return refresh();
    },
    onError: (error: Error) => toast.error(error.message || "Could not roll back"),
  });

  const rows = versions.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Version history</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          A snapshot of the project&apos;s design — entities, fields,
          relationships, rules — that you can compare against and roll back
          to. Generated data is not included; this is the schema, not a
          backup.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="w-72"
            placeholder="what is this a snapshot of? (optional)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <Button onClick={() => snapshot.mutate()} disabled={snapshot.isPending}>
            {snapshot.isPending ? "Saving…" : "Snapshot now"}
          </Button>
        </div>

        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No snapshots yet.</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {rows.map((version) => (
              <li key={version.id} className="flex flex-col gap-1 rounded border p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">v{version.version}</span>
                  {version.label && <span>{version.label}</span>}
                  <span className="text-xs text-muted-foreground">
                    {version.created_at.slice(0, 16).replace("T", " ")}
                    {version.created_by_email ? ` · ${version.created_by_email}` : ""}
                  </span>
                  <div className="ml-auto flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setOpenDiff((v) => (v === version.version ? null : version.version))
                      }
                    >
                      {openDiff === version.version ? "Hide changes" : "Changes since"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => rollback.mutate(version.version)}
                      disabled={rollback.isPending}
                    >
                      Roll back
                    </Button>
                  </div>
                </div>
                {openDiff === version.version && (
                  <DiffPanel projectId={projectId} version={version.version} />
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** What has changed between a snapshot and the project as it stands.
 *
 * Comparing against now is the default because "what have I changed since I
 * saved this" is the question people actually ask. */
function DiffPanel({ projectId, version }: { projectId: string; version: number }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const diff = useQuery({
    queryKey: ["project-version-diff", projectId, version],
    queryFn: () => api.diffProjectVersion(accessToken!, projectId, version),
    enabled: !!accessToken,
  });

  if (diff.isPending) return <p className="text-xs text-muted-foreground">Comparing…</p>;
  if (!diff.data) return <p className="text-xs text-destructive">Could not compare.</p>;
  if (diff.data.identical) {
    return (
      <p className="text-xs text-muted-foreground">
        Nothing has changed since this snapshot.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-0.5 border-t pt-1 text-xs text-muted-foreground">
      {lines(diff.data).map((line, index) => (
        <li key={index}>{line}</li>
      ))}
    </ul>
  );
}

/** The diff as sentences.
 *
 * Structural, not textual: a JSON text diff reports a list reordering when
 * nothing changed and buries the one real edit in context. */
function lines(diff: VersionDiff): string[] {
  const out: string[] = [];
  if (diff.name_changed) {
    out.push(`renamed from "${diff.name_changed.before}" to "${diff.name_changed.after}"`);
  }
  for (const name of diff.entities_added) out.push(`+ entity ${name}`);
  for (const name of diff.entities_removed) out.push(`− entity ${name}`);
  for (const entity of diff.entities_changed) {
    for (const field of entity.fields_added) out.push(`+ ${entity.name}.${field}`);
    for (const field of entity.fields_removed) out.push(`− ${entity.name}.${field}`);
    for (const field of entity.fields_changed) {
      for (const [attr, change] of Object.entries(field.changes)) {
        out.push(
          `~ ${entity.name}.${field.name} ${attr}: ` +
            `${JSON.stringify(change.before)} → ${JSON.stringify(change.after)}`
        );
      }
    }
  }
  for (const [section, count] of Object.entries(diff.counts)) {
    if (count.before !== count.after) {
      out.push(`${section.replace(/_/g, " ")}: ${count.before} → ${count.after}`);
    }
  }
  return out;
}
