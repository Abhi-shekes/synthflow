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
import type { Entity } from "@/lib/types";

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
            <div className="flex items-center gap-2">
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
            </div>
            {stores.map((store) => (
              <StoreRow
                key={store.id}
                projectId={projectId}
                entityId={entity.id}
                storeId={store.id}
                storeName={store.name}
                pending={generate.isPending}
                onGenerate={() => generate.mutate(store.id)}
                onDelete={() => remove.mutate(store.id)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** One store's row, with its own stats query so the counts refresh after a
 * generate without refetching every other store on the page. */
function StoreRow({
  projectId,
  entityId,
  storeId,
  storeName,
  pending,
  onGenerate,
  onDelete,
}: {
  projectId: string;
  entityId: string;
  storeId: string;
  storeName: string;
  pending: boolean;
  onGenerate: () => void;
  onDelete: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const stats = useQuery({
    queryKey: ["record-store", projectId, entityId, storeId],
    queryFn: () => api.getRecordStore(accessToken!, projectId, entityId, storeId),
    enabled: !!accessToken,
    // The counts change whenever a generate lands, including one triggered
    // from somewhere other than this page.
    refetchInterval: 5000,
  });

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
      <span className="font-medium">{storeName}</span>
      <span className="text-muted-foreground">
        {stats.data
          ? `${stats.data.active_records} records · position ${stats.data.position}`
          : "…"}
      </span>
      <div className="ml-auto flex gap-2">
        <Button size="sm" variant="outline" onClick={onGenerate} disabled={pending}>
          {pending ? "Generating…" : "Generate"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </div>
  );
}
