"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { useActiveStratum } from "@/components/strata/stratum";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { fieldFill, FIELD_TYPE_ABBR } from "@/lib/field-visual";
import { useDebounced, useReducedMotion } from "@/lib/motion";
import { useAuthStore } from "@/lib/store";
import type { Entity } from "@/lib/types";
import { cn } from "@/lib/utils";

const ROWS = 5;

/**
 * Five live rows, pinned beside the editor.
 *
 * This is the single biggest change in the rebuild. The page this replaces put
 * "Generate" at the bottom of sixteen cards, so the loop was: configure a
 * trend, scroll past nine sections, generate, scroll back to see whether it did
 * what you meant. Here the answer is already on screen.
 *
 * The cost is honest and worth stating: every edit re-runs generation. It is
 * debounced, capped at five rows, and never runs while the tab is hidden — but
 * it is real backend load that the old design did not create.
 */
export function Specimen({
  projectId,
  entity,
  /** Bumped by the page whenever anything about the entity changes. Debounced
   * here rather than at each call site so there is one place that decides how
   * hard this hammers the backend. */
  revision,
}: {
  projectId: string;
  entity: Entity | undefined;
  revision: number;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const active = useActiveStratum();
  const reduced = useReducedMotion();
  const settled = useDebounced(revision, 500);

  const hasFields = !!entity && entity.fields.length > 0;

  const specimen = useQuery({
    queryKey: ["specimen", projectId, entity?.id, settled],
    queryFn: () => api.generate(accessToken!, projectId, entity!.id, ROWS),
    enabled: !!accessToken && hasFields,
    // A specimen is a sample, not a source of truth — refetching it because a
    // window regained focus would churn rows for no new information.
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    retry: false,
  });

  const rows = specimen.data ?? [];
  const fields = entity?.fields ?? [];

  // The one scroll effect that earns its place: reading the Distortion stratum
  // shows the specimen as error injection leaves it. Not decoration — it is the
  // feature demonstrating itself on the rows you already have in view.
  const distorting = active === "distortion" && !reduced;

  return (
    <aside className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <Eyebrow className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block size-1.5 rounded-full",
              specimen.isFetching ? "bg-brand sf-pulse" : "bg-sev-ok"
            )}
          />
          Live specimen
        </Eyebrow>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Regenerate specimen"
          disabled={!hasFields || specimen.isFetching}
          onClick={() => specimen.refetch()}
        >
          <RefreshCw />
        </Button>
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-[var(--shadow-panel)]">
        {!hasFields ? (
          <p className="px-3 py-8 text-center text-xs text-ink-faint">
            Add a field and rows will appear here as you work.
          </p>
        ) : specimen.isError ? (
          <p className="px-3 py-6 text-xs text-sev-crit">
            {(specimen.error as Error).message || "Could not generate a sample."}
          </p>
        ) : rows.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-ink-faint">Generating…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left font-mono text-[13px]">
              <thead>
                <tr className="border-b border-line-soft bg-surface-2">
                  {fields.map((field) => (
                    <th key={field.id} className="px-2 py-1.5 font-medium whitespace-nowrap">
                      <span className="flex items-center gap-1.5">
                        <span
                          aria-hidden
                          className="size-2 shrink-0 rounded-[2px]"
                          style={{ background: fieldFill(field.field_type, field.preset) }}
                        />
                        <span className="text-ink-dim">{field.name}</span>
                        <span className="text-ink-faint">
                          {FIELD_TYPE_ABBR[field.field_type]}
                        </span>
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody
                className={cn(
                  "transition-opacity duration-300",
                  specimen.isFetching && "opacity-40"
                )}
              >
                {rows.map((row, index) => (
                  <tr key={index} className="border-b border-line-soft last:border-b-0">
                    {fields.map((field) => (
                      <Cell
                        key={field.id}
                        value={row[field.name]}
                        // Damage deepens down the sample rather than hitting
                        // every row at once, so you can see what a rate of
                        // injection actually looks like in a batch.
                        damaged={distorting && index >= ROWS - 1 - Math.floor(index / 2)}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-xs leading-relaxed text-ink-faint">
        {ROWS} rows, regenerated as you edit.
        {distorting && " Showing what error injection leaves behind."}
      </p>
    </aside>
  );
}

function Cell({ value, damaged }: { value: unknown; damaged: boolean }) {
  if (damaged) {
    return (
      <td className="px-2 py-1 whitespace-nowrap text-sev-crit/70 line-through">
        {format(value)}
      </td>
    );
  }
  return (
    <td
      className={cn(
        "px-2 py-1 whitespace-nowrap",
        value === null || value === undefined ? "text-ink-faint" : "text-ink-dim"
      )}
    >
      {format(value)}
    </td>
  );
}

function format(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "object") {
    const json = JSON.stringify(value);
    return json.length > 24 ? `${json.slice(0, 24)}…` : json;
  }
  const text = String(value);
  return text.length > 24 ? `${text.slice(0, 24)}…` : text;
}
