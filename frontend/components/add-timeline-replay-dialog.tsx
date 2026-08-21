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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LookupTable, TimelineReplayCreateInput } from "@/lib/types";

interface FormValues {
  lookup_table_id: string;
  timestamp_column: string;
  speed_multiplier: string;
}

export function AddTimelineReplayDialog({
  lookupTables,
  onSubmit,
  isPending,
}: {
  lookupTables: LookupTable[];
  onSubmit: (values: TimelineReplayCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const defaults: FormValues = {
    lookup_table_id: "",
    timestamp_column: "",
    speed_multiplier: "1",
  };
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: defaults,
  });

  const lookupTableId = watch("lookup_table_id");
  const timestampColumn = watch("timestamp_column");
  const speedMultiplier = watch("speed_multiplier");
  const selectedTable = lookupTables.find((t) => t.id === lookupTableId);

  const submit = (values: FormValues) => {
    onSubmit({
      lookup_table_id: values.lookup_table_id,
      timestamp_column: values.timestamp_column,
      speed_multiplier: Number(values.speed_multiplier),
    });
    reset(defaults);
    setOpen(false);
  };

  const canSubmit = !!lookupTableId && !!timestampColumn && Number(speedMultiplier) > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset(defaults);
      }}
    >
      <DialogTrigger render={<Button size="sm" disabled={lookupTables.length === 0} />}>
        Add timeline replay
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add timeline replay</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Lookup table</Label>
            <Select
              value={lookupTableId}
              onValueChange={(v) => {
                setValue("lookup_table_id", v ?? "");
                setValue("timestamp_column", "");
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
              Upload one from the Lookup tables card above first.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Timestamp column</Label>
            <Select
              value={timestampColumn}
              onValueChange={(v) => setValue("timestamp_column", v ?? "")}
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
            <p className="text-xs text-muted-foreground">
              Every row&apos;s value in this column must be an ISO-8601
              timestamp (e.g. 2024-01-01T00:00:00) — rows are replayed in
              that order, not upload order.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="speed_multiplier">Speed multiplier</Label>
            <Input
              id="speed_multiplier"
              type="number"
              step="any"
              min={0.001}
              value={speedMultiplier}
              onChange={(e) => setValue("speed_multiplier", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              1 replays at the original pace; 60 plays a 1-hour gap back in
              1 minute.
            </p>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !canSubmit}>
              {isPending ? "Adding…" : "Add timeline replay"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
