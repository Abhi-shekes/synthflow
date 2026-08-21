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
import { Textarea } from "@/components/ui/textarea";
import type { Entity, WorkflowCreateInput } from "@/lib/types";

interface FormValues {
  field_id: string;
  states: string;
  initial_states: string;
  transitions: string;
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function AddWorkflowDialog({
  entity,
  onSubmit,
  isPending,
}: {
  entity: Entity;
  onSubmit: (values: WorkflowCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      field_id: "",
      states: "",
      initial_states: "",
      transitions: "",
    },
  });

  const fieldsWithoutWorkflow = entity.fields.filter(
    (f) => !entity.workflows.some((w) => w.field_id === f.id)
  );
  const fieldId = watch("field_id");

  const submit = (values: FormValues) => {
    const states = splitList(values.states);
    const initial_states = splitList(values.initial_states);
    const transitions = values.transitions
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [source, target] = line.split("->").map((s) => s.trim());
        return { source, target };
      });

    if (transitions.some((t) => !t.source || !t.target)) {
      setError('Each transition line must look like "source -> target"');
      return;
    }
    setError(null);

    onSubmit({ field_id: values.field_id, states, initial_states, transitions });
    reset();
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          reset();
          setError(null);
        }
      }}
    >
      <DialogTrigger
        render={<Button size="sm" disabled={fieldsWithoutWorkflow.length === 0} />}
      >
        Add workflow
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add workflow</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Field</Label>
            <Select value={fieldId} onValueChange={(v) => setValue("field_id", v ?? "")}>
              <SelectTrigger>
                <SelectValue>
                  {(v: string) =>
                    v ? fieldsWithoutWorkflow.find((f) => f.id === v)?.name : "Select field"
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {fieldsWithoutWorkflow.map((f) => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="states">States (comma-separated)</Label>
            <Input
              id="states"
              placeholder="created, packed, shipped, delivered"
              {...register("states", { required: "At least one state is required" })}
            />
            {errors.states && (
              <p className="text-sm text-destructive">{errors.states.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="initial_states">Initial states (comma-separated subset)</Label>
            <Input
              id="initial_states"
              placeholder="created"
              {...register("initial_states", { required: "At least one initial state is required" })}
            />
            {errors.initial_states && (
              <p className="text-sm text-destructive">{errors.initial_states.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="transitions">Transitions (one per line, &quot;source -&gt; target&quot;)</Label>
            <Textarea
              id="transitions"
              placeholder={"created -> packed\npacked -> shipped\nshipped -> delivered"}
              rows={4}
              {...register("transitions")}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !fieldId}>
              {isPending ? "Adding…" : "Add workflow"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
