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
import { RELATIONSHIP_TYPES, type Entity, type RelationshipCreateInput, type RelationshipType } from "@/lib/types";

interface FormValues {
  relationship_type: RelationshipType;
  source_entity_id: string;
  source_field_id: string;
  target_entity_id: string;
  target_field_id: string;
}

export function AddRelationshipDialog({
  entities,
  onSubmit,
  isPending,
}: {
  entities: Entity[];
  onSubmit: (values: RelationshipCreateInput) => void;
  isPending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { handleSubmit, watch, setValue, reset } = useForm<FormValues>({
    defaultValues: {
      relationship_type: "one_to_many",
      source_entity_id: "",
      source_field_id: "",
      target_entity_id: "",
      target_field_id: "",
    },
  });

  const values = watch();
  const sourceEntity = entities.find((e) => e.id === values.source_entity_id);
  const targetEntity = entities.find((e) => e.id === values.target_entity_id);
  const canSubmit =
    values.source_entity_id &&
    values.source_field_id &&
    values.target_entity_id &&
    values.target_field_id;

  const submit = (v: FormValues) => {
    onSubmit(v);
    reset();
    setOpen(false);
  };

  const entitiesWithFields = entities.filter((e) => e.fields.length > 0);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger
        render={<Button size="sm" disabled={entitiesWithFields.length < 2} />}
      >
        Add relationship
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add relationship</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(submit)}>
          <div className="flex flex-col gap-2">
            <Label>Type</Label>
            <Select
              value={values.relationship_type}
              onValueChange={(v) => setValue("relationship_type", v as RelationshipType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RELATIONSHIP_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type.replaceAll("_", "-")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3 rounded-md border p-3">
            <p className="col-span-2 text-sm font-medium text-muted-foreground">
              Source (the foreign-key field)
            </p>
            <div className="flex flex-col gap-2">
              <Label>Entity</Label>
              <Select
                value={values.source_entity_id}
                onValueChange={(v) => {
                  setValue("source_entity_id", v ?? "");
                  setValue("source_field_id", "");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select entity" />
                </SelectTrigger>
                <SelectContent>
                  {entities.map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Field</Label>
              <Select
                value={values.source_field_id}
                onValueChange={(v) => setValue("source_field_id", v ?? "")}
                disabled={!sourceEntity}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select field" />
                </SelectTrigger>
                <SelectContent>
                  {sourceEntity?.fields.map((f) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.name} ({f.field_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 rounded-md border p-3">
            <p className="col-span-2 text-sm font-medium text-muted-foreground">
              Target (the referenced field)
            </p>
            <div className="flex flex-col gap-2">
              <Label>Entity</Label>
              <Select
                value={values.target_entity_id}
                onValueChange={(v) => {
                  setValue("target_entity_id", v ?? "");
                  setValue("target_field_id", "");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select entity" />
                </SelectTrigger>
                <SelectContent>
                  {entities
                    .filter((e) => e.id !== values.source_entity_id)
                    .map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Field</Label>
              <Select
                value={values.target_field_id}
                onValueChange={(v) => setValue("target_field_id", v ?? "")}
                disabled={!targetEntity}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select field" />
                </SelectTrigger>
                <SelectContent>
                  {targetEntity?.fields.map((f) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.name} ({f.field_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isPending || !canSubmit}>
              {isPending ? "Adding…" : "Add relationship"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
