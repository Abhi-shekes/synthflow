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
import { Textarea } from "@/components/ui/textarea";
import { FIELD_TYPES, type FieldCreateInput, type FieldType } from "@/lib/types";

interface FormValues {
  name: string;
  field_type: FieldType;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  min_value: string;
  max_value: string;
  regex: string;
  enum_values: string;
  enum_weights: string;
  formula: string;
}

export function AddFieldDialog({
  onSubmit,
  isPending,
}: {
  onSubmit: (values: FieldCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      field_type: "string",
      required: false,
      nullable: true,
      unique: false,
      min_value: "",
      max_value: "",
      regex: "",
      enum_values: "",
      enum_weights: "",
      formula: "",
    },
  });

  const fieldType = watch("field_type");
  const formula = watch("formula");

  const submit = (values: FormValues) => {
    onSubmit({
      name: values.name,
      field_type: values.field_type,
      required: values.required,
      nullable: values.nullable,
      unique: values.unique,
      min_value: values.min_value === "" ? null : Number(values.min_value),
      max_value: values.max_value === "" ? null : Number(values.max_value),
      regex: values.regex === "" ? null : values.regex,
      enum_values:
        values.enum_values === ""
          ? null
          : values.enum_values
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
      enum_weights:
        values.enum_weights.trim() === ""
          ? null
          : values.enum_weights
              .split(",")
              .map((v) => Number(v.trim()))
              .filter((n) => !Number.isNaN(n)),
      formula: values.formula === "" ? null : values.formula,
    });
    reset();
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm">Add field</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add field</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name", { required: "Name is required" })} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>

          <div className="flex flex-col gap-2">
            <Label>Type</Label>
            <Select
              value={fieldType}
              onValueChange={(value) => setValue("field_type", value as FieldType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FIELD_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={watch("required")}
                onCheckedChange={(v) => setValue("required", v === true)}
              />
              Required
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={watch("nullable")}
                onCheckedChange={(v) => setValue("nullable", v === true)}
                disabled={!!formula}
              />
              Nullable
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={watch("unique")}
                onCheckedChange={(v) => setValue("unique", v === true)}
                disabled={!!formula}
              />
              Unique
            </label>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="formula">Formula (optional)</Label>
            <Input
              id="formula"
              placeholder="e.g. 100 - temperature * 1.5 + noise(3)"
              {...register("formula")}
            />
            <p className="text-xs text-muted-foreground">
              Computes this field from other fields on the same row instead of
              generating it randomly — this is also how to correlate two
              fields (e.g. humidity falling as temperature rises). Can only
              reference fields added above this one. Functions:{" "}
              <code className="font-mono">abs min max round len</code>, plus{" "}
              <code className="font-mono">noise(stddev)</code> and{" "}
              <code className="font-mono">uniform(low, high)</code> for
              realistic scatter instead of a dead-flat line.
            </p>
          </div>

          {!formula && (fieldType === "integer" || fieldType === "float") && (
            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-2">
                <Label htmlFor="min_value">Min</Label>
                <Input id="min_value" type="number" step="any" {...register("min_value")} />
              </div>
              <div className="flex flex-1 flex-col gap-2">
                <Label htmlFor="max_value">Max</Label>
                <Input id="max_value" type="number" step="any" {...register("max_value")} />
              </div>
            </div>
          )}

          {!formula && fieldType === "string" && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="regex">Regex (optional)</Label>
              <Input id="regex" placeholder="e.g. [A-Z]{3}-[0-9]{4}" {...register("regex")} />
            </div>
          )}

          {!formula && fieldType === "enum" && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="enum_values">Values (comma-separated)</Label>
              <Textarea
                id="enum_values"
                placeholder="bronze, silver, gold"
                {...register("enum_values", {
                  required: fieldType === "enum" ? "At least one value is required" : false,
                })}
              />
              {errors.enum_values && (
                <p className="text-sm text-destructive">{errors.enum_values.message}</p>
              )}
            </div>
          )}

          {!formula && fieldType === "enum" && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="enum_weights">Weights (optional, comma-separated)</Label>
              <Input
                id="enum_weights"
                placeholder="e.g. 65, 25, 10 — one per value, same order"
                {...register("enum_weights", {
                  validate: (value) => {
                    if (value.trim() === "") return true;
                    const valueCount = watch("enum_values")
                      .split(",")
                      .map((v) => v.trim())
                      .filter(Boolean).length;
                    const weightCount = value.split(",").filter((v) => v.trim() !== "").length;
                    return (
                      weightCount === valueCount ||
                      "Must have exactly one weight per value, in the same order"
                    );
                  },
                })}
              />
              {errors.enum_weights && (
                <p className="text-sm text-destructive">{errors.enum_weights.message}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Leave blank for a uniform random choice. Weights don&apos;t need
                to add up to 100 — they&apos;re relative.
              </p>
            </div>
          )}

          <DialogFooter>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Adding…" : "Add field"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
