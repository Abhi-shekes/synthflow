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
import type { Entity, LookupAttachmentCreateInput, LookupTable } from "@/lib/types";

interface FormValues {
  field_id: string;
  lookup_table_id: string;
  column: string;
}

export function AddLookupAttachmentDialog({
  entity,
  lookupTables,
  onSubmit,
  isPending,
}: {
  entity: Entity;
  lookupTables: LookupTable[];
  onSubmit: (values: LookupAttachmentCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const defaults: FormValues = { field_id: "", lookup_table_id: "", column: "" };
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: defaults,
  });

  const availableFields = entity.fields.filter(
    (f) => !entity.lookup_attachments.some((a) => a.field_id === f.id)
  );
  const fieldId = watch("field_id");
  const lookupTableId = watch("lookup_table_id");
  const column = watch("column");
  const selectedTable = lookupTables.find((t) => t.id === lookupTableId);

  const submit = (values: FormValues) => {
    onSubmit(values);
    reset(defaults);
    setOpen(false);
  };

  const canSubmit = !!fieldId && !!lookupTableId && !!column;

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
        Add lookup
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add lookup</DialogTitle>
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
              Only fields without a lookup already attached.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Lookup table</Label>
            <Select
              value={lookupTableId}
              onValueChange={(v) => {
                setValue("lookup_table_id", v ?? "");
                setValue("column", "");
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
          </div>

          <div className="flex flex-col gap-2">
            <Label>Column</Label>
            <Select
              value={column}
              onValueChange={(v) => setValue("column", v ?? "")}
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
              The field draws a real value from this column instead of being
              randomized.
            </p>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !canSubmit}>
              {isPending ? "Adding…" : "Add lookup"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
