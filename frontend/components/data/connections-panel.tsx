"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { AddDatabaseConnectionDialog } from "@/components/add-database-connection-dialog";
import { AddStorageTargetDialog } from "@/components/add-storage-target-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Panel, PanelBody, PanelEmpty, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { DatabaseConnectionCreateInput, Entity } from "@/lib/types";

/**
 * Where generated rows can be written, and where job artifacts can be uploaded.
 *
 * Both are project-scoped credentials rather than per-entity outputs, which is
 * why they live on the Data page and not in an entity's Delivery stratum.
 */
export function ConnectionsPanel({ projectId }: { projectId: string }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

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

  const invalidate = (key: string) =>
    queryClient.invalidateQueries({ queryKey: [key, projectId] });

  const createConnection = useMutation({
    mutationFn: (values: DatabaseConnectionCreateInput) =>
      api.createDatabaseConnection(accessToken!, projectId, values),
    onSuccess: () => invalidate("database-connections"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not add that connection"),
  });

  const deleteConnection = useMutation({
    mutationFn: (id: string) => api.deleteDatabaseConnection(accessToken!, projectId, id),
    onSuccess: () => invalidate("database-connections"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that connection"),
  });

  const testConnection = useMutation({
    mutationFn: (id: string) => api.testDatabaseConnection(accessToken!, projectId, id),
    onSuccess: (result) =>
      result.ok
        ? toast.success(result.detail || "Connected")
        : toast.error(result.detail || "Could not connect"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not reach that database"),
  });

  const testStorage = useMutation({
    mutationFn: (id: string) => api.testStorageTarget(accessToken!, projectId, id),
    onSuccess: (result) =>
      result.ok
        ? toast.success(result.detail || "Bucket reachable")
        : toast.error(result.detail || "Could not reach that bucket"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not reach that bucket"),
  });

  const deleteStorage = useMutation({
    mutationFn: (id: string) => api.deleteStorageTarget(accessToken!, projectId, id),
    onSuccess: () => invalidate("storage-targets"),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that target"),
  });

  const connections = connectionsQuery.data ?? [];
  const targets = storageQuery.data ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel>
        <PanelHeader>
          <PanelTitle>Database connections</PanelTitle>
          <AddDatabaseConnectionDialog
            onSubmit={(v) => createConnection.mutate(v)}
            isPending={createConnection.isPending}
          />
        </PanelHeader>
        <PanelBody className="flex flex-col gap-3">
          <p className="text-xs leading-relaxed text-ink-dim">
            Write generated rows straight into an external database instead of downloading
            them. PostgreSQL, MySQL and MongoDB. Passwords are encrypted at rest.
          </p>
          {connections.length === 0 ? (
            <PanelEmpty>
              No connections yet. Add one to push rows into a real database — or to import a
              schema from it.
            </PanelEmpty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {connections.map((connection) => (
                <li
                  key={connection.id}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-2"
                >
                  <span className="text-xs font-medium">{connection.name}</span>
                  <Badge variant="secondary">{connection.dialect}</Badge>
                  <span className="font-mono text-xs text-ink-faint">
                    {connection.host}:{connection.port}/{connection.database}
                  </span>
                  <div className="ml-auto flex gap-1">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => testConnection.mutate(connection.id)}
                      disabled={testConnection.isPending}
                    >
                      Test
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => deleteConnection.mutate(connection.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle>Object storage</PanelTitle>
          <AddStorageTargetDialog
            projectId={projectId}
            onCreated={() => invalidate("storage-targets")}
          />
        </PanelHeader>
        <PanelBody className="flex flex-col gap-3">
          <p className="text-xs leading-relaxed text-ink-dim">
            Upload a job&apos;s file to a bucket when it finishes — AWS S3, MinIO, R2, Spaces
            or B2. The local artifact is kept either way, so a failed upload never loses a run.
          </p>
          {targets.length === 0 ? (
            <PanelEmpty>
              No storage targets yet. Add one and it becomes selectable when you queue a job.
            </PanelEmpty>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {targets.map((target) => (
                <li
                  key={target.id}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-line-soft bg-surface-2 px-2.5 py-2"
                >
                  <span className="text-xs font-medium">{target.name}</span>
                  <Badge variant="secondary">{target.provider}</Badge>
                  <span className="font-mono text-xs text-ink-faint">
                    s3://{target.bucket}
                    {target.prefix ? `/${target.prefix}` : ""}
                  </span>
                  <div className="ml-auto flex gap-1">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => testStorage.mutate(target.id)}
                      disabled={testStorage.isPending}
                    >
                      Test
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => deleteStorage.mutate(target.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}

/** Write generated rows into one of the connections above. */
export function PushPanel({
  projectId,
  entities,
}: {
  projectId: string;
  entities: Entity[];
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [connectionId, setConnectionId] = useState("");
  const [entityId, setEntityId] = useState("");
  const [count, setCount] = useState(100);

  const connectionsQuery = useQuery({
    queryKey: ["database-connections", projectId],
    queryFn: () => api.listDatabaseConnections(accessToken!, projectId),
    enabled: !!accessToken,
  });

  const push = useMutation({
    mutationFn: () =>
      api.pushToDatabaseConnection(accessToken!, projectId, connectionId, entityId, count),
    onSuccess: (result) =>
      toast.success(`Wrote ${result.rows_written} rows to ${result.table}`),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not push those rows"),
  });

  const connections = connectionsQuery.data ?? [];

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Push rows to a database</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-col gap-3">
        <p className="text-xs leading-relaxed text-ink-dim">
          Generate an entity straight into one of the connections above, rather than
          downloading a file and loading it yourself.
        </p>
        {connections.length === 0 || entities.length === 0 ? (
          <PanelEmpty>
            {connections.length === 0
              ? "Add a database connection first."
              : "This project has no entities to push."}
          </PanelEmpty>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Select value={connectionId} onValueChange={(v) => setConnectionId(v ?? "")}>
              <SelectTrigger className="h-8 w-44 text-xs">
                <SelectValue placeholder="Connection" />
              </SelectTrigger>
              <SelectContent>
                {connections.map((connection) => (
                  <SelectItem key={connection.id} value={connection.id}>
                    {connection.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={entityId} onValueChange={(v) => setEntityId(v ?? "")}>
              <SelectTrigger className="h-8 w-40 text-xs">
                <SelectValue placeholder="Entity" />
              </SelectTrigger>
              <SelectContent>
                {entities.map((entity) => (
                  <SelectItem key={entity.id} value={entity.id}>
                    {entity.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              min={1}
              className="h-8 w-24 text-xs"
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
            <Button
              size="sm"
              disabled={!connectionId || !entityId || push.isPending}
              onClick={() => push.mutate()}
            >
              {push.isPending ? "Pushing…" : "Push"}
            </Button>
          </div>
        )}
      </PanelBody>
    </Panel>
  );
}
