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
import { TREND_PARAMS, TREND_TYPES, type Entity, type TrendCreateInput, type TrendType } from "@/lib/types";

interface FormValues {
  field_id: string;
  trend_type: TrendType;
  params: Record<string, string>;
  noise: string;
}

export function AddTrendDialog({
  entity,
  onSubmit,
  isPending,
}: {
  entity: Entity;
  onSubmit: (values: TrendCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: {
      field_id: "",
      trend_type: "linear",
      params: {},
      noise: "",
    },
  });

  const numericFields = entity.fields.filter(
    (f) =>
      (f.field_type === "integer" || f.field_type === "float") &&
      !entity.trends.some((t) => t.field_id === f.id)
  );
  const fieldId = watch("field_id");
  const trendType = watch("trend_type");
  const params = watch("params");
  const paramNames = TREND_PARAMS[trendType];

  const submit = (values: FormValues) => {
    const parsedParams: Record<string, number> = {};
    for (const name of paramNames) {
      parsedParams[name] = Number(values.params[name] ?? 0);
    }
    if (values.noise.trim() !== "") {
      parsedParams.noise = Number(values.noise);
    }
    onSubmit({ field_id: values.field_id, trend_type: values.trend_type, params: parsedParams });
    reset({ field_id: "", trend_type: "linear", params: {}, noise: "" });
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset({ field_id: "", trend_type: "linear", params: {}, noise: "" });
      }}
    >
      <DialogTrigger render={<Button size="sm" disabled={numericFields.length === 0} />}>
        Add trend
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add trend</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Field</Label>
            <Select value={fieldId} onValueChange={(v) => setValue("field_id", v ?? "")}>
              <SelectTrigger>
                <SelectValue>
                  {(v: string) => (v ? numericFields.find((f) => f.id === v)?.name : "Select field")}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {numericFields.map((f) => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.name} ({f.field_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Only integer/float fields without a trend already attached.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Type</Label>
            <Select
              value={trendType}
              onValueChange={(v) => {
                setValue("trend_type", v as TrendType);
                setValue("params", {});
              }}
            >
              <SelectTrigger>
                <SelectValue>{(v: string) => v.replaceAll("_", " ")}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {TREND_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t.replaceAll("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {paramNames.map((name) => (
              <div key={name} className="flex flex-col gap-2">
                <Label htmlFor={`param-${name}`}>{name}</Label>
                <Input
                  id={`param-${name}`}
                  type="number"
                  step="any"
                  value={params[name] ?? ""}
                  onChange={(e) =>
                    setValue("params", { ...params, [name]: e.target.value })
                  }
                />
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="noise">Noise (optional)</Label>
            <Input
              id="noise"
              type="number"
              step="any"
              min={0}
              placeholder="stddev of random noise added on top"
              onChange={(e) => setValue("noise", e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !fieldId}>
              {isPending ? "Adding…" : "Add trend"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
