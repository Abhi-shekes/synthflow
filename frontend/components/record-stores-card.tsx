"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { ChangeEvent, Entity } from "@/lib/types";

/**
 * Record stores for one entity.
 *
 * A store is the thing that makes two generation calls related: records
 * generated last week are still there this week, and a child entity's
 * foreign keys can point at them. The counts are what make that visible —
 * "12 records" after two calls of six is the feature working, where two
 * unrelated batches of six would have been the old behaviour.
 */
export function RecordStoresCard({
  projectId,
  entity,
}: {
  projectId: string;
  entity: Entity;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const [name, setName] = useState("default");
  const [identityFieldId, setIdentityFieldId] = useState("");
  const [count, setCount] = useState(10);
  const [inserts, setInserts] = useState(2);
  const [updates, setUpdates] = useState(3);
  const [deletes, setDeletes] = useState(1);

  const storesQuery = useQuery({
    queryKey: ["record-stores", projectId, entity.id],
    queryFn: () => api.listRecordStores(accessToken!, projectId, entity.id),
    enabled: !!accessToken,
  });

  const stores = storesQuery.data ?? [];

  // A nullable field cannot identify a record, and the API refuses one — so
  // it is not offered here either. Showing an option the server will reject
  // is a worse way to teach the rule than not showing it.
  const identityCandidates = entity.fields.filter((f) => !f.nullable);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["record-stores", projectId, entity.id] });

  const create = useMutation({
    mutationFn: () => {
      if (!identityFieldId) throw new Error("Choose the field that identifies a record");
      return api.createRecordStore(accessToken!, projectId, entity.id, {
        name: name.trim() || "default",
        identity_field_id: identityFieldId,
      });
    },
    onSuccess: (store) => {
      toast.success(`Store "${store.name}" created`);
      setName("default");
      return invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Could not create that store"),
  });

  const generate = useMutation({
    mutationFn: (storeId: string) =>
      api.generateIntoStore(accessToken!, projectId, entity.id, storeId, count),
    onSuccess: (result) =>
      toast.success(
        `${result.rows.length} added — ${result.total_active} records in the store now`
      ),
    onError: (error: Error) => toast.error(error.message || "Could not generate into that store"),
  });

  const churn = useMutation({
    mutationFn: (storeId: string) =>
      api.applyChanges(accessToken!, projectId, entity.id, storeId, {
        inserts,
        updates,
        deletes,
      }),
    onSuccess: (result) =>
      toast.success(
        `${result.events.length} change${result.events.length === 1 ? "" : "s"} — ` +
          `${result.total_active} records active`
      ),
    onError: (error: Error) => toast.error(error.message || "Could not apply changes"),
  });

  const remove = useMutation({
    mutationFn: (storeId: string) =>
      api.deleteRecordStore(accessToken!, projectId, entity.id, storeId),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(error.message || "Could not delete that store"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Record stores</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          A store keeps this entity&apos;s records between generation calls, so
          the same customer exists tomorrow and can receive new orders. Trends
          and geo routes continue from where the last call stopped instead of
          replaying from their start.
        </p>

        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`store-name-${entity.id}`}>Name</Label>
            <Input
              id={`store-name-${entity.id}`}
              className="w-40"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Identifies a record</Label>
            <Select
              value={identityFieldId}
              onValueChange={(v) => setIdentityFieldId(v ?? "")}
            >
              <SelectTrigger className="w-52">
                <SelectValue>
                  {(v: string) =>
                    identityCandidates.find((f) => f.id === v)?.name ?? "choose a field"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {identityCandidates.map((f) => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.name} ({f.field_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || identityCandidates.length === 0}
          >
            {create.isPending ? "Creating…" : "Add store"}
          </Button>
        </div>

        {identityCandidates.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Every field on this entity is nullable. A record needs a
            non-nullable field to identify it — a null identity joins to
            nothing.
          </p>
        )}

        {stores.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No stores yet. Without one, every generation call produces a fresh
            unrelated set of records.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Label htmlFor={`store-count-${entity.id}`} className="text-xs">
                Records per call
              </Label>
              <Input
                id={`store-count-${entity.id}`}
                type="number"
                min={1}
                className="w-24"
                value={count}
                onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
              />
              <span className="ml-4 text-xs text-muted-foreground">Per tick of change:</span>
              {(
                [
                  ["insert", inserts, setInserts],
                  ["update", updates, setUpdates],
                  ["delete", deletes, setDeletes],
                ] as const
              ).map(([label, value, set]) => (
                <span key={label} className="flex items-center gap-1">
                  <Label
                    htmlFor={`store-${label}-${entity.id}`}
                    className="text-xs text-muted-foreground"
                  >
                    {label}
                  </Label>
                  <Input
                    id={`store-${label}-${entity.id}`}
                    type="number"
                    min={0}
                    className="w-16"
                    value={value}
                    onChange={(e) => set(Math.max(0, Number(e.target.value) || 0))}
                  />
                </span>
              ))}
            </div>
            {stores.map((store) => (
              <StoreRow
                key={store.id}
                projectId={projectId}
                entityId={entity.id}
                storeId={store.id}
                storeName={store.name}
                pending={generate.isPending}
                churning={churn.isPending}
                onGenerate={() => generate.mutate(store.id)}
                onChurn={() => churn.mutate(store.id)}
                onDelete={() => remove.mutate(store.id)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** One store's row: what is in it, and what has been happening to it.
 *
 * The change log is collapsed by default. It is the most interesting thing
 * on the card and also the longest — a store driven for a while has more
 * events than fit next to a control panel. */
function StoreRow({
  projectId,
  entityId,
  storeId,
  storeName,
  pending,
  churning,
  onGenerate,
  onChurn,
  onDelete,
}: {
  projectId: string;
  entityId: string;
  storeId: string;
  storeName: string;
  pending: boolean;
  churning: boolean;
  onGenerate: () => void;
  onChurn: () => void;
  onDelete: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [showLog, setShowLog] = useState(false);

  const stats = useQuery({
    queryKey: ["record-store", projectId, entityId, storeId],
    queryFn: () => api.getRecordStore(accessToken!, projectId, entityId, storeId),
    enabled: !!accessToken,
    // The counts change whenever a generate or a tick lands, including one
    // triggered from somewhere other than this page.
    refetchInterval: 5000,
  });

  const log = useQuery({
    queryKey: ["record-store-changes", projectId, entityId, storeId],
    queryFn: () => api.readChanges(accessToken!, projectId, entityId, storeId, -1, 200),
    enabled: !!accessToken && showLog,
    refetchInterval: showLog ? 5000 : false,
  });

  // Newest first: the last thing that happened is what someone watching a
  // stream wants to see, and scrolling to the bottom of a growing log to
  // find it is the wrong way round.
  const events = [...(log.data ?? [])].reverse();

  return (
    <div className="flex flex-col gap-2 rounded-md border p-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{storeName}</span>
        <span className="text-muted-foreground">
          {stats.data
            ? `${stats.data.active_records} records · ${stats.data.deleted_records} deleted · position ${stats.data.position}`
            : "…"}
        </span>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" onClick={onGenerate} disabled={pending}>
            {pending ? "Generating…" : "Generate"}
          </Button>
          <Button size="sm" variant="outline" onClick={onChurn} disabled={churning}>
            {churning ? "Applying…" : "Apply changes"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowLog((s) => !s)}>
            {showLog ? "Hide log" : "Change log"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      {showLog && (
        <div className="max-h-64 overflow-y-auto rounded border bg-muted/30 p-2">
          {events.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Nothing has changed yet. Generate records, then apply a tick of
              change.
            </p>
          ) : (
            <ul className="flex flex-col gap-1 font-mono text-xs">
              {events.map((event) => (
                <li key={event.sequence} className="flex gap-2">
                  <span className="w-10 shrink-0 text-muted-foreground">
                    {event.sequence}
                  </span>
                  <span className="w-14 shrink-0 font-medium">{event.operation}</span>
                  <span className="truncate">{describe(event)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** What actually moved, rather than the whole row.
 *
 * An update between two twenty-column rows is unreadable printed in full,
 * and the one thing a reader wants from it is which columns changed —
 * which is exactly what keeping `before` alongside `after` makes possible. */
function describe(event: ChangeEvent): string {
  if (event.operation === "insert") return `${event.identity}`;
  if (event.operation === "delete") return `${event.identity} (was v${event.version - 1})`;

  const before = event.before ?? {};
  const after = event.after ?? {};
  const moved = Object.keys(after).filter(
    (key) => JSON.stringify(before[key]) !== JSON.stringify(after[key])
  );
  if (moved.length === 0) return `${event.identity} — no column changed`;
  const shown = moved
    .slice(0, 3)
    .map((key) => `${key}: ${JSON.stringify(before[key])} → ${JSON.stringify(after[key])}`)
    .join(", ");
  return moved.length > 3 ? `${shown}, +${moved.length - 3} more` : shown;
}
