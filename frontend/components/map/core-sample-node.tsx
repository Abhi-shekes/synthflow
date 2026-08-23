"use client";

import { Handle, Position, useStore, type NodeProps } from "@xyflow/react";
import Link from "next/link";

import { fieldFill, FIELD_TYPE_ABBR, isPiiPreset } from "@/lib/field-visual";
import { useTilt } from "@/lib/motion";
import type { Entity } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface CoreSampleData extends Record<string, unknown> {
  entity: Entity;
  projectId: string;
}

/** Level of detail. Reading a 40-field list at 30% zoom is not reading, and
 * drawing it costs a DOM node per field per entity on every pan. */
const NEAR = 1.15;
const MID = 0.7;

/**
 * An entity as a **core sample** — a stack of bands, one per field, coloured by
 * type, hatched where the field holds personal data.
 *
 * The point is that composition is legible before any text is: a string-heavy
 * table with three PII columns and a float-dominant sensor reading look nothing
 * alike from across the room. And because the picture is generated from the
 * schema rather than drawn, it cannot go stale.
 */
export function CoreSampleNode({ data, selected }: NodeProps) {
  const { entity, projectId } = data as CoreSampleData;
  const zoom = useStore((state) => state.transform[2]);
  const { ref, tiltProps } = useTilt<HTMLDivElement>();

  const detail = zoom >= NEAR ? "near" : zoom >= MID ? "mid" : "far";
  const piiCount = entity.fields.filter((f) => isPiiPreset(f.preset)).length;

  return (
    <div
      ref={ref}
      {...tiltProps}
      className={cn(
        "w-56 overflow-hidden rounded-xl border bg-surface shadow-[var(--shadow-panel)] transition-colors",
        selected ? "border-brand" : "border-line"
      )}
    >
      <Handle type="target" position={Position.Left} className="!size-2" />
      <Handle type="source" position={Position.Right} className="!size-2" />

      <div className="flex items-start justify-between gap-2 px-3 pt-2.5 pb-2">
        <div className="min-w-0">
          <Link
            href={`/projects/${projectId}/entities/${entity.id}`}
            className="block truncate font-display text-sm font-semibold tracking-tight hover:underline"
          >
            {entity.name}
          </Link>
          {detail !== "far" && (
            <p className="mt-0.5 font-mono text-xs text-ink-faint">
              {entity.fields.length} field{entity.fields.length === 1 ? "" : "s"}
              {piiCount > 0 && ` · ${piiCount} pii`}
            </p>
          )}
        </div>
      </div>

      {/* The core sample itself. Horizontal bands, top to bottom in field order,
          so the shape matches the row's column order. */}
      <div className="flex flex-col gap-px px-3 pb-2.5">
        {entity.fields.length === 0 ? (
          <p className="py-2 text-center font-mono text-xs text-ink-faint">no fields</p>
        ) : (
          entity.fields.map((field) => (
            <div key={field.id} className="group/band relative">
              <span
                className="block h-2.5 rounded-[2px]"
                style={{ background: fieldFill(field.field_type, field.preset) }}
              />
              {detail === "near" && (
                <span className="pointer-events-none absolute inset-0 flex items-center justify-between px-1.5">
                  <span className="truncate font-mono text-[8px] leading-none font-medium text-ground mix-blend-luminosity">
                    {field.name}
                  </span>
                  <span className="shrink-0 font-mono text-[8px] leading-none text-ground/70 mix-blend-luminosity">
                    {FIELD_TYPE_ABBR[field.field_type]}
                  </span>
                </span>
              )}
            </div>
          ))
        )}
      </div>

      {detail === "near" && entity.fields.length > 0 && (
        <div className="flex flex-wrap gap-1 border-t border-line-soft px-3 py-1.5">
          {entity.rules.length > 0 && <Tag>{entity.rules.length} rules</Tag>}
          {entity.trends.length > 0 && <Tag>{entity.trends.length} trends</Tag>}
          {entity.workflows.length > 0 && <Tag>{entity.workflows.length} workflows</Tag>}
          {entity.error_injections.length > 0 && (
            <Tag>{entity.error_injections.length} injections</Tag>
          )}
        </div>
      )}
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-surface-2 px-1.5 font-mono text-[9px] text-ink-faint">
      {children}
    </span>
  );
}

/** A source or destination — deliberately smaller and quieter than an entity.
 * They are context for the pipeline, not the thing being designed. */
export function TerminalNode({ data }: NodeProps) {
  const { label, detail, color, side } = data as {
    label: string;
    detail: string;
    color: string;
    side: "source" | "destination";
  };

  return (
    <div
      className="w-40 rounded-lg border border-line bg-surface px-2.5 py-2"
      style={{ borderLeftColor: color, borderLeftWidth: 3 }}
    >
      {side === "destination" ? (
        <Handle type="target" position={Position.Left} className="!size-2" />
      ) : (
        <Handle type="source" position={Position.Right} className="!size-2" />
      )}
      <p className="truncate text-xs font-medium">{label}</p>
      <p className="truncate font-mono text-[9px] text-ink-faint">{detail}</p>
    </div>
  );
}
