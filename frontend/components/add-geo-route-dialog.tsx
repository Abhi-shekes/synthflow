"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Entity, GeoRouteCreateInput, LookupTable } from "@/lib/types";

interface FormValues {
  field_id: string;
  lookup_table_id: string;
  lat_column: string;
  lon_column: string;
}

export function AddGeoRouteDialog({
  entity,
  lookupTables,
  onSubmit,
  isPending,
}: {
  entity: Entity;
  lookupTables: LookupTable[];
  onSubmit: (values: GeoRouteCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const defaults: FormValues = {
    field_id: "",
    lookup_table_id: "",
    lat_column: "",
    lon_column: "",
  };
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: defaults,
  });

  const availableFields = entity.fields.filter(
    (f) =>
      (f.field_type === "object" || f.field_type === "json") &&
      !entity.geo_routes.some((g) => g.field_id === f.id)
  );
  const fieldId = watch("field_id");
  const lookupTableId = watch("lookup_table_id");
  const latColumn = watch("lat_column");
  const lonColumn = watch("lon_column");
  const selectedTable = lookupTables.find((t) => t.id === lookupTableId);

  const submit = (values: FormValues) => {
    onSubmit(values);
    reset(defaults);
    setOpen(false);
  };

  const canSubmit = !!fieldId && !!lookupTableId && !!latColumn && !!lonColumn;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset(defaults);
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" disabled={availableFields.length === 0 || lookupTables.length === 0} />
        }
      >
        Add geo route
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add geo route</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Field</Label>
            <Select value={fieldId} onValueChange={(v) => setValue("field_id", v ?? "")}>
              <SelectTrigger>
                <SelectValue>
                  {(v: string) => (v ? availableFields.find((f) => f.id === v)?.name : "Select field")}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {availableFields.map((f) => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.name} ({f.field_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Only object/json fields without a geo route already attached
              — the value becomes {"{"}
              &quot;lat&quot;, &quot;lon&quot;
              {"}"}.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Lookup table (waypoints)</Label>
            <Select
              value={lookupTableId}
              onValueChange={(v) => {
                setValue("lookup_table_id", v ?? "");
                setValue("lat_column", "");
                setValue("lon_column", "");
              }}
            >
              <SelectTrigger>
                <SelectValue>
                  {(v: string) =>
                    v ? lookupTables.find((t) => t.id === v)?.name : "Select table"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {lookupTables.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name} ({t.row_count} rows)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Rows are the route&apos;s waypoints in upload order — upload
              one from the project page first.
            </p>
          </div>

          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-2">
              <Label>Latitude column</Label>
              <Select
                value={latColumn}
                onValueChange={(v) => setValue("lat_column", v ?? "")}
                disabled={!selectedTable}
              >
                <SelectTrigger>
                  <SelectValue>{(v: string) => v || "Select column"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {selectedTable?.columns.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-1 flex-col gap-2">
              <Label>Longitude column</Label>
              <Select
                value={lonColumn}
                onValueChange={(v) => setValue("lon_column", v ?? "")}
                disabled={!selectedTable}
              >
                <SelectTrigger>
                  <SelectValue>{(v: string) => v || "Select column"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {selectedTable?.columns.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            The field&apos;s value walks this path, interpolated across the
            generated batch — row 0 is the first waypoint, the last row is
            the last waypoint, regardless of how many rows you generate.
          </p>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !canSubmit}>
              {isPending ? "Adding…" : "Add geo route"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
