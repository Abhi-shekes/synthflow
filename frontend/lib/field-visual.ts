import type { FieldType } from "@/lib/types";

/**
 * The one field-type colour system.
 *
 * Every surface that shows a field reads from here: the system map's core
 * samples, field tables, generated-data headers, the schema-import diff, the
 * quality and privacy reports. The point is that you learn to read a schema's
 * composition by colour, so the mapping has to be the same everywhere — hence
 * one module rather than a `switch` per component.
 *
 * The values are CSS custom properties, not hex, so light and dark resolve
 * from globals.css instead of being branched on here.
 */
export const FIELD_TYPE_COLOR: Record<FieldType, string> = {
  string: "var(--t-string)",
  integer: "var(--t-integer)",
  float: "var(--t-float)",
  boolean: "var(--t-boolean)",
  date: "var(--t-date)",
  datetime: "var(--t-datetime)",
  uuid: "var(--t-uuid)",
  enum: "var(--t-enum)",
  array: "var(--t-array)",
  object: "var(--t-object)",
  json: "var(--t-json)",
};

/** Short label for tight spaces — core-sample tooltips, table chips. */
export const FIELD_TYPE_ABBR: Record<FieldType, string> = {
  string: "str",
  integer: "int",
  float: "flt",
  boolean: "bool",
  date: "date",
  datetime: "dt",
  uuid: "uuid",
  enum: "enum",
  array: "arr",
  object: "obj",
  json: "json",
};

/**
 * Personal-data presets, mirroring the backend's `PiiPreset` enum.
 *
 * Hardcoded rather than fetched, because a core sample has to decide whether
 * to hatch a band while it renders — an extra round trip per node is not worth
 * it for a fixed enum. `GET /generator-plugins` returns these too (with
 * `category: "pii"`), and that list stays the source of truth for the *picker*;
 * this one only answers "should this band be hatched?".
 */
export const PII_PRESETS = new Set([
  "person_name",
  "first_name",
  "last_name",
  "email_address",
  "phone_number",
  "street_address",
  "full_address",
  "postcode",
  "city",
  "payment_card",
  "ssn",
  "aadhaar",
  "ip_address",
  "username",
  "company_name",
  "date_of_birth",
]);

export function isPiiPreset(preset: string | null | undefined): boolean {
  return !!preset && PII_PRESETS.has(preset);
}

/**
 * The fill for a field's band or swatch.
 *
 * PII gets a hatch rather than its own hue on purpose: "this column is personal
 * data" is a different axis from "this column is a string", and collapsing them
 * into one scale would mean you could no longer read type and sensitivity at
 * the same time.
 */
export function fieldFill(fieldType: FieldType, preset?: string | null): string {
  const color = FIELD_TYPE_COLOR[fieldType];
  if (!isPiiPreset(preset)) return color;
  return `repeating-linear-gradient(-45deg, ${color} 0 3px, color-mix(in srgb, ${color} 40%, var(--surface)) 3px 6px)`;
}

/** A tint of the field's hue, for chip and row backgrounds. */
export function fieldTint(fieldType: FieldType, percent = 12): string {
  return `color-mix(in srgb, ${FIELD_TYPE_COLOR[fieldType]} ${percent}%, transparent)`;
}

/** Output-kind accents, so a destination reads the same on the map, in the
 * delivery stratum, and in the outputs table. */
export const OUTPUT_COLOR: Record<string, string> = {
  database: "var(--t-object)",
  rest: "var(--t-string)",
  websocket: "var(--t-float)",
  kafka: "var(--t-enum)",
  mqtt: "var(--t-datetime)",
  rabbitmq: "var(--t-json)",
  webhook: "var(--t-boolean)",
  plugin: "var(--t-array)",
  timeline_replay: "var(--t-date)",
  storage: "var(--t-integer)",
};

/**
 * One colour per top-level project section (VISUAL_POLISH_PLAN.md V2) —
 * reused for its rail link, its `SectionHeader`, and its hero panel's
 * `tone="marked"` accent, so all three agree on what "this section" looks
 * like. Most entries reuse an existing hue rather than invent one:
 * `delivery` is REST's colour in `OUTPUT_COLOR`, `monitor` is the same
 * "this is running" green used elsewhere for live state. `data` and
 * `governance` get colours of their own because nothing existing fits
 * without giving an already-meaningful colour a second, different meaning.
 */
export const SECTION_COLOR = {
  map: "var(--brand)",
  data: "var(--sec-data)",
  delivery: "var(--t-string)",
  monitor: "var(--sev-ok)",
  governance: "var(--sec-governance)",
} as const;

export type SectionKey = keyof typeof SECTION_COLOR;

export const OUTPUT_LABEL: Record<string, string> = {
  database: "Database",
  rest: "REST",
  websocket: "WebSocket",
  kafka: "Kafka",
  mqtt: "MQTT",
  rabbitmq: "RabbitMQ",
  webhook: "Webhook",
  plugin: "Plugin",
  timeline_replay: "Replay",
  storage: "Object storage",
};
