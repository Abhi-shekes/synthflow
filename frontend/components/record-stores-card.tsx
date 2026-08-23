"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type {
  ChangeEvent,
  Entity,
  RecordVersion,
  SCDType,
  StoredRecord,
} from "@/lib/types";

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
  const [scdType, setScdType] = useState<SCDType>("type_1");
  const [inserts, setInserts] = useState(2);
  const [updates, setUpdates] = useState(3);
  const [deletes, setDeletes] = useState(1);
  const [backfillDays, setBackfillDays] = useState(30);
  const [backfillTicks, setBackfillTicks] = useState(30);

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
        scd_type: scdType,
      });
    },
    onSuccess: (store) => {
      toast.success(`Store "${store.name}" created`);
      setName("default");
      return invalidate();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create that store"),
  });

  const generate = useMutation({
    mutationFn: (storeId: string) =>
      api.generateIntoStore(accessToken!, projectId, entity.id, storeId, count),
    onSuccess: (result) =>
      toast.success(
        `${result.rows.length} added — ${result.total_active} records in the store now`
      ),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not generate into that store"),
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
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not apply changes"),
  });

  const backfill = useMutation({
    mutationFn: (storeId: string) => {
      const end = new Date();
      const start = new Date(end.getTime() - backfillDays * 86_400_000);
      return api.backfillStore(accessToken!, projectId, entity.id, storeId, {
        start: start.toISOString(),
        end: end.toISOString(),
        ticks: backfillTicks,
        inserts,
        updates,
        deletes,
      });
    },
    onSuccess: (result) =>
      toast.success(
        `${result.events_written} events across ${backfillDays} days — ` +
          `${result.total_active} records active`
      ),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not backfill"),
  });

  const remove = useMutation({
    mutationFn: (storeId: string) =>
      api.deleteRecordStore(accessToken!, projectId, entity.id, storeId),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that store"),
  });

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Record stores</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-col gap-4">
        <p className="text-xs leading-relaxed text-ink-dim">
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
          <div className="flex flex-col gap-1">
            <Label>History</Label>
            <Select value={scdType} onValueChange={(v) => setScdType((v ?? "type_1") as SCDType)}>
              <SelectTrigger className="w-56">
                <SelectValue>
                  {(v: string) =>
                    v === "type_2" ? "Type 2 — keep every version" : "Type 1 — overwrite"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="type_1">Type 1 — overwrite</SelectItem>
                <SelectItem value="type_2">Type 2 — keep every version</SelectItem>
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
          <p className="text-xs text-ink-faint">
            Every field on this entity is nullable. A record needs a
            non-nullable field to identify it — a null identity joins to
            nothing.
          </p>
        )}

        {stores.length === 0 ? (
          <p className="text-xs leading-relaxed text-ink-dim">
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
              <span className="ml-4 text-xs text-ink-faint">Per tick of change:</span>
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
                    className="text-xs text-ink-faint"
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
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-ink-faint">Backfill:</span>
              <Label htmlFor={`store-days-${entity.id}`} className="text-xs text-ink-faint">
                days back
              </Label>
              <Input
                id={`store-days-${entity.id}`}
                type="number"
                min={1}
                className="w-20"
                value={backfillDays}
                onChange={(e) => setBackfillDays(Math.max(1, Number(e.target.value) || 1))}
              />
              <Label htmlFor={`store-ticks-${entity.id}`} className="text-xs text-ink-faint">
                ticks
              </Label>
              <Input
                id={`store-ticks-${entity.id}`}
                type="number"
                min={1}
                className="w-20"
                value={backfillTicks}
                onChange={(e) => setBackfillTicks(Math.max(1, Number(e.target.value) || 1))}
              />
              <span className="text-xs text-ink-faint">
                — same per-tick counts, dated across the window. Backfill a new
                store <em>before</em> generating live: history has to come
                first, or records created today end up with versions that end
                before they start.
              </span>
            </div>
            {stores.map((store) => (
              <StoreRow
                key={store.id}
                projectId={projectId}
                entityId={entity.id}
                storeId={store.id}
                storeName={store.name}
                scdType={store.scd_type}
                pending={generate.isPending}
                churning={churn.isPending}
                backfilling={backfill.isPending}
                onGenerate={() => generate.mutate(store.id)}
                onChurn={() => churn.mutate(store.id)}
                onBackfill={() => backfill.mutate(store.id)}
                onDelete={() => remove.mutate(store.id)}
              />
            ))}
          </div>
        )}
      </PanelBody>
    </Panel>
  );
}

/** One store's row: what is in it, and what has been happening to it.
 *
 * The change log and the version history are collapsed by default. They are
 * the most interesting things on the card and also the longest — a store
 * driven for a while has more of both than fit next to a control panel. */
function StoreRow({
  projectId,
  entityId,
  storeId,
  storeName,
  scdType,
  pending,
  churning,
  backfilling,
  onGenerate,
  onChurn,
  onBackfill,
  onDelete,
}: {
  projectId: string;
  entityId: string;
  storeId: string;
  storeName: string;
  scdType: SCDType;
  pending: boolean;
  churning: boolean;
  backfilling: boolean;
  onGenerate: () => void;
  onChurn: () => void;
  onBackfill: () => void;
  onDelete: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [panel, setPanel] = useState<"none" | "records" | "log" | "history">("none");
  const [identity, setIdentity] = useState("");

  const stats = useQuery({
    queryKey: ["record-store", projectId, entityId, storeId],
    queryFn: () => api.getRecordStore(accessToken!, projectId, entityId, storeId),
    enabled: !!accessToken,
    // The counts change whenever a generate, a tick or a backfill lands,
    // including one triggered from somewhere other than this page.
    refetchInterval: 5000,
  });

  // What is actually in the store. `GET .../records` has existed since Phase 13
  // and nothing called it — you could generate into a store, churn it and read
  // its change log, but never look at the records themselves.
  const records = useQuery({
    queryKey: ["record-store-records", projectId, entityId, storeId],
    queryFn: () => api.listStoredRecords(accessToken!, projectId, entityId, storeId, 50),
    enabled: !!accessToken && panel === "records",
  });

  const log = useQuery({
    queryKey: ["record-store-changes", projectId, entityId, storeId],
    queryFn: () => api.readChanges(accessToken!, projectId, entityId, storeId, -1, 200),
    enabled: !!accessToken && panel === "log",
    refetchInterval: panel === "log" ? 5000 : false,
  });

  const history = useQuery({
    queryKey: ["record-store-versions", projectId, entityId, storeId, identity],
    queryFn: () =>
      api.listRecordVersions(accessToken!, projectId, entityId, storeId, { identity }),
    enabled: !!accessToken && panel === "history" && identity.length > 0,
  });

  // Newest first: the last thing that happened is what someone watching a
  // stream wants to see, and scrolling to the bottom of a growing log to
  // find it is the wrong way round.
  const events = [...(log.data ?? [])].reverse();

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-2.5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{storeName}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-ink-faint">
          {scdType === "type_2" ? "type 2" : "type 1"}
        </span>
        <span className="text-muted-foreground">
          {stats.data
            ? `${stats.data.active_records} records · ${stats.data.deleted_records} deleted · position ${stats.data.position}`
            : "…"}
        </span>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={onGenerate} disabled={pending}>
            {pending ? "Generating…" : "Generate"}
          </Button>
          <Button size="sm" variant="outline" onClick={onChurn} disabled={churning}>
            {churning ? "Applying…" : "Apply changes"}
          </Button>
          <Button size="sm" variant="outline" onClick={onBackfill} disabled={backfilling}>
            {backfilling ? "Backfilling…" : "Backfill"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setPanel((p) => (p === "records" ? "none" : "records"))}
          >
            {panel === "records" ? "Hide records" : "Browse records"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setPanel((p) => (p === "log" ? "none" : "log"))}
          >
            {panel === "log" ? "Hide log" : "Change log"}
          </Button>
          {scdType === "type_2" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setPanel((p) => (p === "history" ? "none" : "history"))}
            >
              {panel === "history" ? "Hide history" : "History"}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      {panel === "records" && <RecordBrowser query={records} />}

      {panel === "log" && (
        <div className="max-h-64 overflow-y-auto rounded border bg-muted/30 p-2">
          {events.length === 0 ? (
            <p className="text-xs text-ink-faint">
              Nothing has changed yet. Generate records, then apply a tick of
              change or backfill a window.
            </p>
          ) : (
            <ul className="flex flex-col gap-1 font-mono text-xs">
              {events.map((event) => (
                <li key={event.sequence} className="flex gap-2">
                  <span className="w-10 shrink-0 text-muted-foreground">{event.sequence}</span>
                  <span className="w-14 shrink-0 font-medium">{event.operation}</span>
                  <span className="w-28 shrink-0 text-muted-foreground">
                    {event.event_time.slice(0, 16).replace("T", " ")}
                  </span>
                  <span className="truncate">{describe(event)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {panel === "history" && (
        <div className="flex flex-col gap-2 rounded border bg-muted/30 p-2">
          <div className="flex items-center gap-2">
            <Label htmlFor={`store-identity-${storeId}`} className="text-xs">
              Record
            </Label>
            <Input
              id={`store-identity-${storeId}`}
              className="w-96 font-mono text-xs"
              placeholder="paste an identity from the change log"
              value={identity}
              onChange={(e) => setIdentity(e.target.value.trim())}
            />
          </div>
          {identity.length === 0 ? (
            <p className="text-xs text-ink-faint">
              A type 2 store keeps every version of a record. Name one to see
              how it changed and when each version was the truth.
            </p>
          ) : history.data && history.data.length > 0 ? (
            <ul className="flex flex-col gap-1 font-mono text-xs">
              {history.data.map((version) => (
                <li key={version.id} className="flex gap-2">
                  <span className="w-8 shrink-0 text-muted-foreground">v{version.version}</span>
                  <span className="w-56 shrink-0 text-muted-foreground">
                    {version.valid_from.slice(0, 16).replace("T", " ")} →{" "}
                    {version.valid_to
                      ? version.valid_to.slice(0, 16).replace("T", " ")
                      : "now"}
                  </span>
                  <span className="truncate">{summarise(version)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-faint">
              No versions for that identity.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * The store's contents as a table.
 *
 * Columns are derived from the union of keys across the returned rows rather
 * than from the entity's field list: a type 2 store can hold versions written
 * before a field was added, and showing a column the older rows never had is
 * more honest than hiding one they do.
 *
 * Deleted records are shown, struck through, not filtered out — in a store with
 * soft deletes "where did that row go?" is the question, and an empty table
 * answers it badly.
 */
function RecordBrowser({
  query,
}: {
  query: UseQueryResult<StoredRecord[], Error>;
}) {
  if (query.isPending) {
    return (
      <p className="rounded border border-line-soft bg-surface-2 p-2 text-xs text-ink-faint">
        Loading records…
      </p>
    );
  }
  if (query.isError) {
    return (
      <p className="rounded border border-line-soft bg-surface-2 p-2 text-xs text-sev-crit">
        {query.error.message || "Could not read records."}
      </p>
    );
  }

  const rows = query.data ?? [];
  if (rows.length === 0) {
    return (
      <p className="rounded border border-line-soft bg-surface-2 p-2 text-xs text-ink-faint">
        This store is empty. Generate into it and the records will appear here.
      </p>
    );
  }

  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row.data))));

  return (
    <div className="max-h-72 overflow-auto rounded border border-line-soft bg-surface-2">
      <table className="w-full border-collapse text-left font-mono text-[13px]">
        <thead className="sticky top-0 bg-surface-3">
          <tr>
            <th className="px-2 py-1.5 font-medium text-ink-faint">identity</th>
            <th className="px-2 py-1.5 font-medium text-ink-faint">v</th>
            {columns.map((column) => (
              <th key={column} className="px-2 py-1.5 font-medium whitespace-nowrap text-ink-dim">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className={
                row.status === "deleted"
                  ? "border-t border-line-soft text-ink-faint line-through"
                  : "border-t border-line-soft"
              }
            >
              <td className="max-w-40 truncate px-2 py-1 text-ink-dim">{row.identity}</td>
              <td className="px-2 py-1 text-ink-faint">{row.version}</td>
              {columns.map((column) => (
                <td key={column} className="px-2 py-1 whitespace-nowrap">
                  {format(row.data[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A cell value, short enough to sit on one line. */
function format(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") {
    const json = JSON.stringify(value);
    return json.length > 40 ? `${json.slice(0, 40)}…` : json;
  }
  return String(value);
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

/** A version's values, trimmed to what fits on one line. */
function summarise(version: RecordVersion): string {
  const parts = Object.entries(version.data)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`);
  return parts.join(", ");
}
