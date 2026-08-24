import { FIELD_TYPE_COLOR } from "@/lib/field-visual";

/** Reuses the field-type scale rather than a generic red-to-green meter, so
 * the one moment the form judges an input speaks the same visual language as
 * the rest of the product. */
const BANDS: (keyof typeof FIELD_TYPE_COLOR)[] = ["string", "integer", "enum", "boolean"];
const LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"];

function score(value: string): number {
  if (!value) return 0;
  let points = 0;
  if (value.length >= 8) points += 1;
  if (value.length >= 12) points += 1;
  if (/[0-9]/.test(value) && /[a-zA-Z]/.test(value)) points += 1;
  if (/[^a-zA-Z0-9]/.test(value)) points += 1;
  return Math.min(points, BANDS.length);
}

export function PasswordStrength({ value }: { value: string }) {
  if (!value) return null;
  const filled = score(value);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-1">
        {BANDS.map((type, i) => (
          <span
            key={type}
            className="h-1 flex-1 rounded-full transition-colors duration-200"
            style={{ background: i < filled ? FIELD_TYPE_COLOR[type] : "var(--line)" }}
          />
        ))}
      </div>
      <p className="sr-only" aria-live="polite">
        {LABELS[filled]} password
      </p>
    </div>
  );
}
