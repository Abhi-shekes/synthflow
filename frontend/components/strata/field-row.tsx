"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Trash2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { fieldFill, FIELD_TYPE_ABBR, isPiiPreset } from "@/lib/field-visual";
import { useAuthStore } from "@/lib/store";
import { FIELD_TYPES, type EntityField, type FieldType, type FieldUpdateInput } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * One field, readable at a glance and editable in place.
 *
 * Editing is new. `PATCH .../fields/{id}` has existed the whole time and the UI
 * never called it, so changing a field's type or its null rate meant deleting
 * it and building it again — losing its position, and any trend, injection or
 * workflow that pointed at it.
 */
export function FieldRow({
  projectId,
  entityId,
  field,
  onChanged,
}: {
  projectId: string;
  entityId: string;
  field: EntityField;
  onChanged: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<FieldUpdateInput>({});

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["entity", projectId, entityId] });
    onChanged();
  };

  const update = useMutation({
    mutationFn: (patch: FieldUpdateInput) =>
      api.updateField(accessToken!, projectId, entityId, field.id, patch),
    onSuccess: () => {
      toast.success(`${field.name} updated`);
      setOpen(false);
      setDraft({});
      invalidate();
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not update that field"),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteField(accessToken!, projectId, entityId, field.id),
    onSuccess: invalidate,
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete that field"),
  });

  // Only what actually changed goes to the server. The backend applies
  // `exclude_unset`, so sending the whole field back would overwrite anything a
  // concurrent edit had changed in the meantime.
  const dirty = Object.keys(draft).length > 0;
  const value = <K extends keyof FieldUpdateInput>(key: K): FieldUpdateInput[K] =>
    key in draft ? draft[key] : (field[key as keyof EntityField] as FieldUpdateInput[K]);

  const set = (patch: FieldUpdateInput) => setDraft((prev) => ({ ...prev, ...patch }));

  const pii = isPiiPreset(field.preset);

  return (
    <li
      id={`field-${field.id}`}
      className="rounded-lg border border-line-soft bg-surface-2 transition-colors target:border-brand"
    >
      <div className="flex flex-wrap items-center gap-2 px-2.5 py-2">
        <span
          aria-hidden
          className="h-4 w-1 shrink-0 rounded-full"
          style={{ background: fieldFill(field.field_type, field.preset) }}
        />
        <span className="font-mono text-xs font-medium">{field.name}</span>
        <span className="font-mono text-xs text-ink-faint">
          {FIELD_TYPE_ABBR[field.field_type]}
        </span>

        {pii && (
          <span className="rounded bg-sev-note/10 px-1.5 font-mono text-xs text-sev-note">
            personal data
          </span>
        )}
        {field.required && <Flag>required</Flag>}
        {field.unique && <Flag>unique</Flag>}
        {field.null_probability !== null && (
          <Flag>{Math.round(field.null_probability * 100)}% null</Flag>
        )}
        {field.formula && (
          <span className="truncate font-mono text-xs text-ink-faint">= {field.formula}</span>
        )}
        {field.preset && !pii && (
          <span className="font-mono text-xs text-ink-faint">{field.preset}</span>
        )}

        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="xs"
            aria-expanded={open}
            onClick={() => {
              setOpen((v) => !v);
              setDraft({});
            }}
          >
            {open ? "Cancel" : "Edit"}
            <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`Delete ${field.name}`}
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`Delete the field "${field.name}"?`)) remove.mutate();
            }}
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      {open && (
        <div className="flex flex-col gap-3 border-t border-line-soft px-2.5 py-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Labelled htmlFor={`name-${field.id}`} label="Name">
              <Input
                id={`name-${field.id}`}
                className="h-7 font-mono text-xs"
                value={String(value("name") ?? "")}
                onChange={(e) => set({ name: e.target.value })}
              />
            </Labelled>

            <Labelled label="Type">
              <Select
                value={String(value("field_type") ?? field.field_type)}
                onValueChange={(v) => set({ field_type: (v ?? field.field_type) as FieldType })}
              >
                <SelectTrigger className="h-7 w-full text-xs">
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
            </Labelled>
          </div>

          <div className="flex flex-wrap gap-4">
            <Toggle
              id={`required-${field.id}`}
              label="Required"
              checked={!!value("required")}
              onChange={(next) => set({ required: next })}
            />
            <Toggle
              id={`nullable-${field.id}`}
              label="Nullable"
              checked={!!value("nullable")}
              onChange={(next) => set({ nullable: next })}
            />
            <Toggle
              id={`unique-${field.id}`}
              label="Unique"
              checked={!!value("unique")}
              onChange={(next) => set({ unique: next })}
            />
          </div>

          {/* Only meaningful for a field that can be null at all — a required
              field is never null whatever this says, so offering the input
              there would be offering a setting with no effect. */}
          {!!value("nullable") && !value("required") && (
            <Labelled htmlFor={`null-${field.id}`} label="Null rate (%)">
              <Input
                id={`null-${field.id}`}
                type="number"
                min={0}
                max={100}
                className="h-7 w-28 text-xs"
                placeholder="engine default"
                value={
                  value("null_probability") === null || value("null_probability") === undefined
                    ? ""
                    : Math.round((value("null_probability") as number) * 100)
                }
                onChange={(e) =>
                  set({
                    // Empty clears it back to "unspecified", which is a real
                    // third state and not the same as 0 — see FieldUpdateInput.
                    null_probability:
                      e.target.value === "" ? null : Number(e.target.value) / 100,
                  })
                }
              />
            </Labelled>
          )}

          {(value("field_type") === "integer" || value("field_type") === "float") && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Labelled htmlFor={`min-${field.id}`} label="Minimum">
                <Input
                  id={`min-${field.id}`}
                  type="number"
                  className="h-7 text-xs"
                  value={(value("min_value") as number | null) ?? ""}
                  onChange={(e) =>
                    set({ min_value: e.target.value === "" ? null : Number(e.target.value) })
                  }
                />
              </Labelled>
              <Labelled htmlFor={`max-${field.id}`} label="Maximum">
                <Input
                  id={`max-${field.id}`}
                  type="number"
                  className="h-7 text-xs"
                  value={(value("max_value") as number | null) ?? ""}
                  onChange={(e) =>
                    set({ max_value: e.target.value === "" ? null : Number(e.target.value) })
                  }
                />
              </Labelled>
            </div>
          )}

          <Labelled htmlFor={`formula-${field.id}`} label="Formula">
            <Input
              id={`formula-${field.id}`}
              className="h-7 font-mono text-xs"
              placeholder="price * quantity"
              value={(value("formula") as string | null) ?? ""}
              onChange={(e) => set({ formula: e.target.value || null })}
            />
          </Labelled>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              disabled={!dirty || update.isPending}
              onClick={() => update.mutate(draft)}
            >
              <Check />
              {update.isPending ? "Saving…" : "Save"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setOpen(false);
                setDraft({});
              }}
            >
              <X />
              Discard
            </Button>
            {dirty && (
              <span className="font-mono text-xs text-ink-faint">
                {Object.keys(draft).length} change{Object.keys(draft).length === 1 ? "" : "s"}
              </span>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function Flag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-surface-3 px-1.5 font-mono text-xs text-ink-faint">
      {children}
    </span>
  );
}

function Labelled({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={htmlFor} className="eyebrow">
        {label}
      </Label>
      {children}
    </div>
  );
}

function Toggle({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <Label htmlFor={id} className="flex cursor-pointer items-center gap-1.5 text-xs">
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(!!v)} />
      {label}
    </Label>
  );
}
