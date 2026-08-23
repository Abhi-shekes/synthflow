import { cn } from "@/lib/utils";

/**
 * The SynthFlow mark: a core sample.
 *
 * Four bands of unequal width in field-type colours — the same device the
 * system map uses to draw an entity, at logo size. The identity and the
 * product's one distinctive visualisation are deliberately the same object, so
 * the first thing you see on the sign-in page is the thing you spend the day
 * reading on the canvas.
 *
 * Colours come from CSS custom properties so the mark follows the theme. The
 * favicon and social images can't resolve those, so `app/icon.svg` and the
 * generated images carry the dark-palette hex values directly — if the scale
 * ever changes, those three files change with it.
 */
export function Mark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("size-6 shrink-0", className)}
    >
      <rect x="3" y="3.5" width="18" height="3.2" rx="1.1" fill="var(--t-string)" />
      <rect x="3" y="8.1" width="13" height="3.2" rx="1.1" fill="var(--t-float)" />
      <rect x="3" y="12.7" width="18" height="3.2" rx="1.1" fill="var(--t-enum)" />
      <rect x="3" y="17.3" width="9" height="3.2" rx="1.1" fill="var(--brand)" />
    </svg>
  );
}

/**
 * Mark plus wordmark. `SynthFlow` is one word, capital S and F — the one
 * spelling used across the UI, the docs and the package name.
 */
export function Wordmark({
  className,
  markClassName,
}: {
  className?: string;
  markClassName?: string;
}) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <Mark className={markClassName} />
      <span className="font-display font-bold tracking-tight">SynthFlow</span>
    </span>
  );
}
