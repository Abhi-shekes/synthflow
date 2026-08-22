"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
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
  SelectGroup,
  SelectItem,
  SelectLabel,
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
  /** A percentage as typed, so an empty box stays "unspecified" rather than
   * collapsing to 0 — the two mean different things. */
  null_percent: string;
  min_value: string;
  max_value: string;
  regex: string;
  preset: string;
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
      null_percent: "",
      min_value: "",
      max_value: "",
      regex: "",
      preset: "",
      enum_values: "",
      enum_weights: "",
      formula: "",
    },
  });

  const fieldType = watch("field_type");
  const formula = watch("formula");
  const regex = watch("regex");
  const preset = watch("preset");

  const accessToken = useAuthStore((s) => s.accessToken);
  const presetsQuery = useQuery({
    queryKey: ["generator-plugins"],
    queryFn: () => api.listGeneratorPlugins(accessToken!),
    enabled: !!accessToken && open,
  });
  const presets = presetsQuery.data ?? [];
  const logPresets = presets.filter((p) => p.category === "log");
  const identifierPresets = presets.filter((p) => p.category === "identifier");

  const ruleFunctionsQuery = useQuery({
    queryKey: ["rule-functions"],
    queryFn: () => api.listRuleFunctions(accessToken!),
    enabled: !!accessToken && open,
  });
  const pluginRuleFunctions = (ruleFunctionsQuery.data ?? []).filter(
    (f) => f.source !== "builtin"
  );
  const pluginPresets = presets.filter((p) => p.category === "plugin");

  const submit = (values: FormValues) => {
    onSubmit({
      name: values.name,
      field_type: values.field_type,
      required: values.required,
      nullable: values.nullable,
      unique: values.unique,
      // Blank means unspecified, which the server reads as "use the engine
      // default". A required field never sends one at all — the server
      // refuses the combination rather than storing a value it would then
      // ignore.
      null_probability:
        values.required || !values.nullable || values.null_percent.trim() === ""
          ? null
          : Number(values.null_percent) / 100,
      min_value: values.min_value === "" ? null : Number(values.min_value),
      max_value: values.max_value === "" ? null : Number(values.max_value),
      regex: values.regex === "" ? null : values.regex,
      preset: values.preset === "" ? null : values.preset,
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

          {watch("nullable") && !watch("required") && !formula && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="null_percent">Missing values (optional)</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="null_percent"
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  className="w-24"
                  placeholder="15"
                  {...register("null_percent")}
                />
                <span className="text-sm text-muted-foreground">% of rows are null</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Leave blank for the default 15%. Learning from a sample file
                fills this in with the rate that column actually had, so a
                column that was 3% empty generates 3% nulls. Zero is a real
                answer and means never null.
              </p>
            </div>
          )}

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
              realistic scatter instead of a dead-flat line. If this entity
              has a relationship to another one, you can also reference{" "}
              <code className="font-mono">RelatedEntity.field</code> (e.g.{" "}
              <code className="font-mono">price * Customer.discount_rate</code>
              ) — only works when generating the whole project, not this
              entity alone.
              {pluginRuleFunctions.length > 0 && (
                <>
                  {" "}
                  From installed plugins:{" "}
                  <code className="font-mono">
                    {pluginRuleFunctions.map((f) => f.name).join(" ")}
                  </code>
                  .
                </>
              )}
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
              <Input
                id="regex"
                placeholder="e.g. [A-Z]{3}-[0-9]{4}"
                disabled={!!preset}
                {...register("regex")}
              />
            </div>
          )}

          {!formula && fieldType === "string" && (
            <div className="flex flex-col gap-2">
              <Label>Preset (optional)</Label>
              <Select
                value={preset}
                onValueChange={(v) => setValue("preset", v ?? "")}
                disabled={!!regex}
              >
                <SelectTrigger>
                  <SelectValue>
                    {(v: string) => (v ? v.replaceAll("_", " ") : "None")}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Log & security events</SelectLabel>
                    {logPresets.map((p) => (
                      <SelectItem key={p.name} value={p.name}>
                        {p.name.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                  <SelectGroup>
                    <SelectLabel>Identifiers & codes</SelectLabel>
                    {identifierPresets.map((p) => (
                      <SelectItem key={p.name} value={p.name}>
                        {p.name.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                  {pluginPresets.length > 0 && (
                    <SelectGroup>
                      <SelectLabel>Plugins</SelectLabel>
                      {pluginPresets.map((p) => (
                        <SelectItem key={p.name} value={p.name}>
                          {p.name.replaceAll("_", " ")} ({p.source})
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  )}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Generates a realistic single-line log/security event (e.g. an
                nginx access line), a format-valid synthetic identifier (e.g.
                a PAN, VIN, or QR code), or a value from an installed
                third-party generator plugin, instead of a random word.
                Mutually exclusive with regex.
              </p>
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
              <p className="text-xs text-muted-foreground">
                A value that looks numeric (e.g. a status code like{" "}
                <span className="font-mono">200</span>) is generated as a
                real number, not text.
              </p>
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
