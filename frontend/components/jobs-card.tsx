"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

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
import { api } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { useAuthStore } from "@/lib/store";
import type { Entity, JobFormat } from "@/lib/types";

const ACTIVE = new Set(["queued", "running"]);

/**
 * Jobs and schedules for a project.
 *
 * Polls while anything is queued or running and stops otherwise, rather
 * than refetching on a fixed timer forever — a project whose jobs have
 * all finished shouldn't keep hitting the API.
 */
export function JobsCard({ projectId, entities }: { projectId: string; entities: Entity[] }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const [rows, setRows] = useState(100000);
  const [format, setFormat] = useState<JobFormat>("csv");
  const [entityId, setEntityId] = useState<string>("");
  const [scheduleName, setScheduleName] = useState("");
  const [cronExpr, setCronExpr] = useState("0 2 * * *");

  const jobsQuery = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => api.listJobs(accessToken!, projectId),
    enabled: !!accessToken,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((j) => ACTIVE.has(j.status)) ? 1000 : false,
  });

  const schedulesQuery = useQuery({
    queryKey: ["schedules", projectId],
    queryFn: () => api.listSchedules(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const invalidateJobs = () =>
    queryClient.invalidateQueries({ queryKey: ["jobs", projectId] });

  const createJob = useMutation({
    mutationFn: () =>
      api.createJob(accessToken!, projectId, {
        entity_id: entityId || null,
        rows,
        format,
      }),
    onSuccess: invalidateJobs,
    onError: (e: Error) => toast.error(e.message || "Could not queue the job"),
  });

  const cancelJob = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(accessToken!, projectId, jobId),
    onSuccess: invalidateJobs,
    onError: (e: Error) => toast.error(e.message || "Could not cancel"),
  });

  const download = useMutation({
    mutationFn: async (args: { jobId: string; name: string; format: JobFormat }) => {
      const blob = await api.downloadJobArtifact(
        accessToken!,
        projectId,
        args.jobId,
        args.name
      );
      downloadBlob(blob, `${args.name}.${args.format === "csv" ? "csv" : "jsonl"}`);
    },
    onError: (e: Error) => toast.error(e.message || "Could not download"),
  });

  const createSchedule = useMutation({
    mutationFn: () =>
      api.createSchedule(accessToken!, projectId, {
        name: scheduleName,
        cron: cronExpr,
        rows,
        format,
        entity_id: entityId || null,
      }),
    onSuccess: () => {
      setScheduleName("");
      queryClient.invalidateQueries({ queryKey: ["schedules", projectId] });
    },
    onError: (e: Error) => toast.error(e.message || "Could not create the schedule"),
  });

  const deleteSchedule = useMutation({
    mutationFn: (id: string) => api.deleteSchedule(accessToken!, projectId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules", projectId] }),
    onError: (e: Error) => toast.error(e.message || "Could not delete the schedule"),
  });

  const entityName = (id: string | null) =>
    id === null ? "whole project" : (entities.find((e) => e.id === id)?.name ?? "?");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Generation jobs</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          A job generates in the background and streams rows straight to a file,
          so it isn&apos;t limited by what fits in one response — millions of rows
          are fine. Progress updates while it runs, and it survives a backend
          restart.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <Select value={entityId} onValueChange={(v) => setEntityId(v ?? "")}>
            <SelectTrigger className="w-44">
              <SelectValue>
                {(v: string) => (v ? entityName(v) : "Whole project")}
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
          <div className="flex items-center gap-1 text-sm">
            <span className="text-muted-foreground">rows</span>
            <Input
              type="number"
              min={1}
              value={rows}
              onChange={(e) => setRows(Number(e.target.value))}
              className="w-32"
            />
          </div>
          <Select value={format} onValueChange={(v) => setFormat((v ?? "csv") as JobFormat)}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="csv">csv</SelectItem>
              <SelectItem value="jsonl">jsonl</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={() => createJob.mutate()}
            disabled={createJob.isPending || entities.length === 0}
          >
            {createJob.isPending ? "Queueing…" : "Run job"}
          </Button>
        </div>

        {jobsQuery.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No jobs yet.</p>
        )}

        {jobsQuery.data && jobsQuery.data.length > 0 && (
          <ul className="flex flex-col gap-2">
            {jobsQuery.data.slice(0, 8).map((job) => {
              const pct =
                job.requested_rows > 0
                  ? Math.min(100, Math.round((job.rows_written / job.requested_rows) * 100))
                  : 0;
              return (
                <li key={job.id} className="rounded-md border px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs">{job.status}</span>
                      <span className="text-muted-foreground">
                        {entityName(job.entity_id)} · {job.rows_written.toLocaleString()} /{" "}
                        {job.requested_rows.toLocaleString()} rows
                        {job.schedule_id ? " · scheduled" : ""}
                      </span>
                    </span>
                    <span className="flex shrink-0 gap-1">
                      {ACTIVE.has(job.status) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => cancelJob.mutate(job.id)}
                        >
                          Cancel
                        </Button>
                      )}
                      {job.artifacts &&
                        Object.keys(job.artifacts).map((name) => (
                          <Button
                            key={name}
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              download.mutate({ jobId: job.id, name, format: job.format })
                            }
                          >
                            {name}
                          </Button>
                        ))}
                    </span>
                  </div>
                  {ACTIVE.has(job.status) && (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded bg-muted">
                      <div className="h-full bg-foreground/60" style={{ width: `${pct}%` }} />
                    </div>
                  )}
                  {job.error && (
                    <p className="mt-1 text-xs text-destructive">{job.error}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <div className="flex flex-col gap-2 border-t pt-4">
          <p className="text-sm font-medium">Schedules</p>
          <p className="text-sm text-muted-foreground">
            Run the settings above on a repeating schedule. A scheduled run
            queues an ordinary job, so it gets the same progress and artifacts.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              placeholder="name, e.g. nightly refresh"
              value={scheduleName}
              onChange={(e) => setScheduleName(e.target.value)}
              className="w-52"
            />
            <Input
              placeholder="cron, e.g. 0 2 * * *"
              value={cronExpr}
              onChange={(e) => setCronExpr(e.target.value)}
              className="w-40 font-mono"
            />
            <Button
              variant="outline"
              onClick={() => createSchedule.mutate()}
              disabled={createSchedule.isPending || !scheduleName || !cronExpr}
            >
              {createSchedule.isPending ? "Saving…" : "Add schedule"}
            </Button>
          </div>

          {schedulesQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No schedules yet.</p>
          )}
          {schedulesQuery.data && schedulesQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {schedulesQuery.data.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <span className="truncate">
                    <span className="font-medium">{s.name}</span>{" "}
                    <span className="text-muted-foreground">
                      — {s.description} · {s.requested_rows.toLocaleString()} rows ·{" "}
                      {entityName(s.entity_id)}
                      {s.next_run_at
                        ? ` · next ${new Date(s.next_run_at).toLocaleString()}`
                        : ""}
                    </span>
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => deleteSchedule.mutate(s.id)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
