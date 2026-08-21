"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import {
  ERROR_TYPE_FIELD_RESTRICTIONS,
  ERROR_TYPES,
  type Entity,
  type ErrorInjectionCreateInput,
  type ErrorType,
  type FieldType,
} from "@/lib/types";

interface FormValues {
  field_id: string;
  rate: string;
  error_types: ErrorType[];
}

function errorTypesFor(fieldType: FieldType): ErrorType[] {
  return ERROR_TYPES.filter((t) => {
    const restriction = ERROR_TYPE_FIELD_RESTRICTIONS[t];
    return !restriction || restriction.includes(fieldType);
  });
}

export function AddErrorInjectionDialog({
  entity,
  onSubmit,
  isPending,
}: {
  entity: Entity;
  onSubmit: (values: ErrorInjectionCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const defaults: FormValues = { field_id: "", rate: "0.1", error_types: [] };
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: defaults,
  });

  const availableFields = entity.fields.filter(
    (f) => !entity.error_injections.some((e) => e.field_id === f.id)
  );
  const fieldId = watch("field_id");
  const rate = watch("rate");
  const errorTypes = watch("error_types");
  const selectedField = availableFields.find((f) => f.id === fieldId);
  const applicableTypes = selectedField ? errorTypesFor(selectedField.field_type) : [];

  const submit = (values: FormValues) => {
    onSubmit({
      field_id: values.field_id,
      rate: Number(values.rate),
      error_types: values.error_types,
    });
    reset(defaults);
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset(defaults);
      }}
    >
      <DialogTrigger render={<Button size="sm" disabled={availableFields.length === 0} />}>
        Add error injection
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add error injection</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Field</Label>
            <Select
              value={fieldId}
              onValueChange={(v) => {
                setValue("field_id", v ?? "");
                setValue("error_types", []);
              }}
            >
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
              Only fields without error injection already attached.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="rate">Rate</Label>
            <Input
              id="rate"
              type="number"
              step="0.01"
              min={0.01}
              max={1}
              value={rate}
              onChange={(e) => setValue("rate", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Fraction of generated rows (0–1) that get a corrupted value for this field.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Error types</Label>
            {!selectedField && (
              <p className="text-sm text-muted-foreground">Select a field first.</p>
            )}
            {selectedField && (
              <div className="grid grid-cols-2 gap-2">
                {applicableTypes.map((t) => (
                  <label key={t} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={errorTypes.includes(t)}
                      onCheckedChange={(checked) =>
                        setValue(
                          "error_types",
                          checked === true
                            ? [...errorTypes, t]
                            : errorTypes.filter((existing) => existing !== t)
                        )
                      }
                    />
                    {t.replaceAll("_", " ")}
                  </label>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !fieldId || errorTypes.length === 0}>
              {isPending ? "Adding…" : "Add error injection"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
