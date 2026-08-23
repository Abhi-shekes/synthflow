/**
 * The single source of plain-language explanations for SynthFlow's jargon.
 *
 * `<Term id="k_anonymity">` (components/help/term.tsx), the context help
 * panel (components/help/help-panel.tsx), and the Learn page all read from
 * this one map rather than writing their own copy — a definition changes in
 * one place instead of drifting across three. See SIMPLICITY_PLAN.md §2 and
 * Track A.4.
 */
export interface GlossaryEntry {
  /** The term as it appears in the UI. */
  term: string;
  /** One or two plain-language sentences. No jargon inside the explanation
   * itself — if it needs its own gloss, it's the wrong word to use here. */
  plain: string;
  /** A concrete example, when an abstract definition alone wouldn't land. */
  example?: string;
}

export type GlossaryId =
  | "k_anonymity"
  | "l_diversity"
  | "quasi_identifier"
  | "event_trigger"
  | "trend"
  | "geo_route"
  | "lookup_attachment"
  | "error_injection"
  | "formula"
  | "rule"
  | "workflow"
  | "rest_output"
  | "websocket_output"
  | "kafka_output"
  | "rabbitmq_output"
  | "mqtt_output"
  | "webhook_output"
  | "plugin_output"
  | "pii"
  | "null_rate";

// Explicitly typed as `Record<GlossaryId, GlossaryEntry>` — not inferred —
// so every entry is uniformly a `GlossaryEntry` (optional `example` and
// all) rather than TypeScript remembering which entries happen to omit it.
// `GLOSSARY[id]` for a generic `id: GlossaryId` needs that uniformity;
// without it, an entry lacking `example` narrows the indexed-access type
// and `.example` stops type-checking for every caller, not just that entry.
export const GLOSSARY: Record<GlossaryId, GlossaryEntry> = {
  k_anonymity: {
    term: "k-anonymity",
    plain:
      "How many rows share the exact same combination of the columns you picked. If the smallest group is only 1 row, that row is identifiable even without a name attached.",
    example: "If 5 rows all have the same zip code + birth year, that group has k = 5.",
  },
  l_diversity: {
    term: "l-diversity",
    plain:
      "On top of k-anonymity: within each group, how many different values the sensitive column actually takes. A group can be large (high k) and still leak information if everyone in it shares the same sensitive value.",
    example:
      "10 people in one group all sharing the same diagnosis (l = 1) leaks the diagnosis even though the group is large.",
  },
  quasi_identifier: {
    term: "quasi-identifier",
    plain:
      "A column that, combined with a few others, could point back to one real person — even though no single one of them is a name or ID.",
    example: "Zip code, birth date, and gender together can identify most people uniquely.",
  },
  event_trigger: {
    term: "event trigger",
    plain: "A rule that fires an action automatically when a value crosses a threshold you set.",
    example: "\"When temperature > 90, emit an overheating alert.\"",
  },
  trend: {
    term: "trend",
    plain:
      "A shape a numeric value follows over time instead of being purely random — rising, falling, cycling, or drifting.",
    example: "A seasonal trend makes ice-cream sales rise every summer and fall every winter.",
  },
  geo_route: {
    term: "geo route",
    plain: "A path of GPS coordinates a record moves along over time, instead of staying put.",
    example: "A delivery truck's location updating every few seconds along a real street route.",
  },
  lookup_attachment: {
    term: "lookup table",
    plain:
      "A fixed list of values a field picks from instead of generating one at random — useful when the real values are known in advance.",
    example: "A \"store\" field that always picks from your actual 12 store names, not invented ones.",
  },
  error_injection: {
    term: "error injection",
    plain:
      "Deliberately breaking a fraction of rows — missing values, wrong types, garbled text — so you can test how your system handles bad data before it happens for real.",
  },
  formula: {
    term: "formula",
    plain: "A field whose value is calculated from other fields instead of generated on its own.",
    example: "Total = Price × Quantity",
  },
  rule: {
    term: "rule",
    plain:
      "A condition every generated row must satisfy. Rows that fail it are discarded and regenerated rather than kept.",
    example: "\"age must be 18 or older.\"",
  },
  workflow: {
    term: "workflow",
    plain: "A set of states a record moves through in order, instead of just existing as one row.",
    example: "Created → Packed → Shipped → Delivered.",
  },
  rest_output: {
    term: "REST endpoint",
    plain: "A URL your own app can call to fetch generated rows on demand, like any other API.",
  },
  websocket_output: {
    term: "live stream (WebSocket)",
    plain: "A connection that keeps pushing new rows to a listener in real time, instead of one batch.",
  },
  kafka_output: {
    term: "Kafka",
    plain: "A high-throughput message queue, popular for streaming data between backend services.",
  },
  rabbitmq_output: {
    term: "RabbitMQ",
    plain: "A message queue similar to Kafka, common where messages need reliable delivery and routing.",
  },
  mqtt_output: {
    term: "MQTT",
    plain: "A lightweight messaging protocol built for IoT devices and unreliable networks.",
  },
  webhook_output: {
    term: "signed webhook",
    plain: "Rows POSTed to a URL you control, with a signature so you can verify they really came from here.",
  },
  plugin_output: {
    term: "plugin output",
    plain: "A delivery target implemented as an installable plugin — for destinations not built in directly.",
  },
  pii: {
    term: "PII",
    plain: "Personally identifiable information — data that could name or trace back to a real person.",
    example: "Full name, email address, phone number, government ID.",
  },
  null_rate: {
    term: "null rate",
    plain: "How often this field comes back empty instead of holding a value, expressed as a percentage.",
  },
};
