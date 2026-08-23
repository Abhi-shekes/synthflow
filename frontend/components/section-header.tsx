import type { LucideIcon } from "lucide-react";

import { Eyebrow } from "@/components/ui/panel";

/**
 * The header for a top-level project/workspace page — System Map, Data,
 * Delivery, Monitor, Governance.
 *
 * Generalizes `Stratum`'s header (colour dot + eyebrow + heading +
 * description) up from "one stratum on the entity page" to "one section of
 * the product." Before this, every one of these pages shared the exact same
 * grey eyebrow/heading/description recipe with nothing but the words to
 * tell them apart — this is what gives each one its own identity, reusing
 * the section's colour from `lib/field-visual.ts`'s `SECTION_COLOR` for the
 * icon badge, the dot, and (by convention at each call site) the page's
 * hero panel accent.
 */
export function SectionHeader({
  icon: Icon,
  color,
  eyebrow,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  color: string;
  eyebrow: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="flex size-9 shrink-0 items-center justify-center rounded-lg"
          style={{ background: `color-mix(in srgb, ${color} 16%, transparent)`, color }}
        >
          <Icon className="size-4.5" />
        </span>
        <div>
          <Eyebrow className="flex items-center gap-1.5">
            <span aria-hidden className="inline-block size-1.5 rounded-full" style={{ background: color }} />
            {eyebrow}
          </Eyebrow>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight">{title}</h1>
          {description && (
            <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-dim">{description}</p>
          )}
        </div>
      </div>
      {action}
    </header>
  );
}
