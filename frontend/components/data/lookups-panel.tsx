"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { toast } from "sonner";

import { AddLookupTableDialog } from "@/components/add-lookup-table-dialog";
import { AddTimelineReplayDialog } from "@/components/add-timeline-replay-dialog";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelEmpty, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { TimelineReplayCreateInput } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

/**
 * Uploaded reference data, and replaying it as a live stream.
 *
 * The two belong together: a replay reads a lookup table against a clock, so a
 * replay cannot exist without one and the picker is empty until a table is
 * uploaded.
 */
export function LookupsPanel({ projectId }: { projectId: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const tablesQuery = useQuery({
    queryKey: ["lookup-tables", projectId],
    queryFn: () => api.listLookupTables(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const replaysQuery = useQuery({
    queryKey: ["timeline-replays", projectId],
    queryFn: () => api.listTimelineReplays(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const invalidate = (key: string) =>
    queryClient.invalidateQueries({ queryKey: [key, projectId] });

  const createTable = useMutation({
    mutationFn: (values: { name: string; file: File }) =>
      api.createLookupTable(accessToken!, projectId, values.name, values.file),
    onSuccess: () => invalidate("lookup-tables"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not upload that file"),
  });

  const deleteTable = useMutation({
    mutationFn: (id: string) => api.deleteLookupTable(accessToken!, projectId, id),
    onSuccess: () => invalidate("lookup-tables"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that table"),
  });

  const createReplay = useMutation({
    mutationFn: (values: TimelineReplayCreateInput) =>
      api.createTimelineReplay(accessToken!, projectId, values),
    onSuccess: () => invalidate("timeline-replays"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create that replay"),
  });

  const deleteReplay = useMutation({
    mutationFn: (id: string) => api.deleteTimelineReplay(accessToken!, projectId, id),
    onSuccess: () => invalidate("timeline-replays"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that replay"),
  });

  const tables = tablesQuery.data ?? [];
  const replays = replaysQuery.data ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel>
        <PanelHeader>
          <PanelTitle>Lookup tables</PanelTitle>
          <AddLookupTableDialog
            onSubmit={(v) => createTable.mutate(v)}
            isPending={createTable.isPending}
          />
        </PanelHeader>
        <PanelBody className="flex flex-col gap-3">
          <p className="text-xs leading-relaxed text-ink-dim">
            Real reference data — product catalogues, postcodes, device registries — that
            fields can draw values from instead of inventing them.
          </p>
          {tables.length === 0 ? (
            <PanelEmpty>
              No lookup tables yet. Upload a CSV or Excel file to make its rows available to
              fields and timeline replays.
            </PanelEmpty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {tables.map((table) => (
                <li
                  key={table.id}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-2"
                >
                  <span className="text-xs font-medium">{table.name}</span>
                  <span className="font-mono text-xs text-ink-faint">
                    {table.row_count} rows · {table.columns.length} columns
                  </span>
                  <Button
                    size="xs"
                    variant="ghost"
                    className="ml-auto"
                    onClick={() => deleteTable.mutate(table.id)}
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
          <PanelTitle>Timeline replays</PanelTitle>
          <AddTimelineReplayDialog
            lookupTables={tables}
            onSubmit={(v) => createReplay.mutate(v)}
            isPending={createReplay.isPending}
          />
        </PanelHeader>
        <PanelBody className="flex flex-col gap-3">
          <p className="text-xs leading-relaxed text-ink-dim">
            Replay a historical dataset as a live stream at any speed. Nothing is generated —
            the rows are the ones you uploaded, paced by their own timestamp column.
          </p>
          {replays.length === 0 ? (
            <PanelEmpty>
              {tables.length === 0
                ? "Upload a lookup table first — a replay walks one against a clock."
                : "No replays yet. Pick a table and its timestamp column to stream it back."}
            </PanelEmpty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {replays.map((replay) => {
                const table = tables.find((t) => t.id === replay.lookup_table_id);
                const url = `${API_URL}/public/replay/${replay.token}`;
                return (
                  <li
                    key={replay.id}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-2"
                  >
                    <span className="text-xs font-medium">{table?.name ?? "a deleted table"}</span>
                    <span className="font-mono text-xs text-ink-faint">
                      {replay.timestamp_column} · {replay.speed_multiplier}×
                    </span>
                    <div className="ml-auto flex gap-1">
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        aria-label="Copy replay URL"
                        onClick={() => {
                          navigator.clipboard.writeText(url);
                          toast.success("Replay URL copied");
                        }}
                      >
                        <Copy />
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => deleteReplay.mutate(replay.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
