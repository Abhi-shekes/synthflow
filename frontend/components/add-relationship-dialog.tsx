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
import { Input } from "@/components/ui/input";
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
  min_links: number;
  max_links: number;
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
      min_links: 1,
      max_links: 3,
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

  const isManyToMany = values.relationship_type === "many_to_many";

  const submit = (v: FormValues) => {
    // The link counts are sent only for many_to_many. The other three types
    // put a foreign key on a row and have nothing to count, so sending them
    // anyway would store numbers that quietly do nothing.
    onSubmit(
      v.relationship_type === "many_to_many"
        ? v
        : {
            relationship_type: v.relationship_type,
            source_entity_id: v.source_entity_id,
            source_field_id: v.source_field_id,
            target_entity_id: v.target_entity_id,
            target_field_id: v.target_field_id,
          }
    );
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
                <SelectValue>{(v: string) => (v || "one_to_many").replaceAll("_", "-")}</SelectValue>
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

          {isManyToMany && (
            <div className="flex flex-col gap-2 rounded-md border p-3">
              <p className="text-sm text-muted-foreground">
                A many-to-many has no foreign key on either side, so both
                fields below are each entity&apos;s <em>own</em> key and
                generation emits a join table pairing them. Each source row
                links to a random number of distinct targets in this range —
                a constant count is the tell that a dataset was generated.
              </p>
              <div className="flex items-center gap-2">
                <Label htmlFor="rel-min-links">Links per row</Label>
                <Input
                  id="rel-min-links"
                  type="number"
                  min={0}
                  className="w-20"
                  value={values.min_links}
                  onChange={(e) =>
                    setValue("min_links", Math.max(0, Number(e.target.value) || 0))
                  }
                />
                <span className="text-sm text-muted-foreground">to</span>
                <Input
                  id="rel-max-links"
                  type="number"
                  min={0}
                  className="w-20"
                  value={values.max_links}
                  onChange={(e) =>
                    setValue("max_links", Math.max(0, Number(e.target.value) || 0))
                  }
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 rounded-md border p-3">
            <p className="col-span-2 text-sm font-medium text-muted-foreground">
              {isManyToMany ? "First side (its own key)" : "Source (the foreign-key field)"}
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
                  <SelectValue>
                    {(v: string) => (v ? entities.find((e) => e.id === v)?.name : "Select entity")}
                  </SelectValue>
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
                  <SelectValue>
                    {(v: string) =>
                      v ? sourceEntity?.fields.find((f) => f.id === v)?.name : "Select field"
                    }
                  </SelectValue>
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
              {isManyToMany ? "Second side (its own key)" : "Target (the referenced field)"}
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
                  <SelectValue>
                    {(v: string) => (v ? entities.find((e) => e.id === v)?.name : "Select entity")}
                  </SelectValue>
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
                  <SelectValue>
                    {(v: string) =>
                      v ? targetEntity?.fields.find((f) => f.id === v)?.name : "Select field"
                    }
                  </SelectValue>
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
