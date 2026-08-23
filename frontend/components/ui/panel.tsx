import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * The surface primitive for the rebuilt UI.
 *
 * Deliberately not `Card`. The old pages stacked sixteen `Card`s at identical
 * weight, which is exactly what made everything look equally important; the
 * fix is a surface with an explicit `tone`, so a page has to say which of its
 * regions is load-bearing rather than defaulting them all to the same.
 *
 * - `raised`  — the default. A real panel with a shadow.
 * - `flat`    — sits inside another panel; no shadow, no ring.
 * - `quiet`   — background-only, for grouping without drawing a box.
 * - `marked`  — carries an accent edge. At most one per screen.
 */
function Panel({
  className,
  tone = "raised",
  accent,
  ...props
}: React.ComponentProps<"section"> & {
  tone?: "raised" | "flat" | "quiet" | "marked";
  /** CSS colour for the `marked` edge. Defaults to the brand accent. */
  accent?: string;
}) {
  return (
    <section
      data-slot="panel"
      data-tone={tone}
      style={accent ? ({ "--panel-accent": accent } as React.CSSProperties) : undefined}
      className={cn(
        "relative rounded-xl",
        tone === "raised" && "border border-line bg-surface shadow-[var(--shadow-panel)]",
        tone === "flat" && "border border-line-soft bg-surface-2",
        tone === "quiet" && "bg-surface-2/50",
        tone === "marked" &&
          "border border-line bg-surface shadow-[var(--shadow-panel)] before:absolute before:inset-y-3 before:left-0 before:w-[3px] before:rounded-full before:bg-[var(--panel-accent,var(--brand))]",
        className
      )}
      {...props}
    />
  );
}

function PanelHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      data-slot="panel-header"
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 border-b border-line-soft px-4 py-3",
        className
      )}
      {...props}
    />
  );
}

function PanelTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      data-slot="panel-title"
      className={cn("font-display text-sm font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

function PanelDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="panel-description"
      className={cn("text-xs leading-relaxed text-ink-dim", className)}
      {...props}
    />
  );
}

function PanelBody({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="panel-body" className={cn("px-4 py-3.5", className)} {...props} />;
}

/** Uppercase micro-label. Section eyebrows, stratum names, stat captions. */
function Eyebrow({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("eyebrow", className)} {...props} />;
}

/**
 * Empty state. Every list in the app had a bare "No trends yet." paragraph;
 * this at least says what the thing is for and leaves room for the action that
 * creates one.
 */
function PanelEmpty({
  className,
  children,
  action,
  ...props
}: React.ComponentProps<"div"> & { action?: React.ReactNode }) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-2.5 rounded-lg border border-dashed border-line px-4 py-5 text-xs leading-relaxed text-ink-dim",
        className
      )}
      {...props}
    >
      <div>{children}</div>
      {action}
    </div>
  );
}

export { Panel, PanelHeader, PanelTitle, PanelDescription, PanelBody, PanelEmpty, Eyebrow };
