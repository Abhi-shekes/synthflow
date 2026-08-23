import type { GlossaryId } from "@/lib/glossary";

export interface HelpTopic {
  title: string;
  /** What this page is for, in one short paragraph. */
  what: string;
  /** The 2-3 things people usually do here. */
  actions: string[];
  glossary?: GlossaryId[];
}

/**
 * Route-keyed, static help content — the context help panel
 * (components/help/help-panel.tsx) and the Learn page both read this.
 *
 * Static on purpose: this is a one-phase, zero-backend-dependency layer.
 * A real assistant (SIMPLICITY_PLAN.md §4 B.5) waits on ROADMAP.md Phase 6
 * (BYO-LLM), which hasn't started — this ships without it.
 *
 * Ordered most-specific pattern first; `match()` returns the first pattern
 * whose regex matches the current pathname.
 */
const TOPICS: { pattern: RegExp; topic: HelpTopic }[] = [
  {
    pattern: /^\/projects\/[^/]+\/entities\/[^/]+/,
    topic: {
      title: "This entity",
      what: "One kind of record in your project — its shape, how it behaves over time, and where its rows go once generated.",
      actions: [
        "Add fields under Shape to define what a row looks like.",
        "Click \"Add rules\" / \"Add behaviour\" to constrain or shape values — optional.",
        "Hit Generate to see sample rows, or Download to export them.",
      ],
      glossary: ["rule", "formula", "trend", "error_injection"],
    },
  },
  {
    pattern: /^\/projects\/[^/]+\/delivery/,
    topic: {
      title: "Delivery",
      what: "Every place this project's data can go, across every entity, in one list.",
      actions: [
        "Download a file or create a REST endpoint for a quick integration.",
        "Open \"Advanced delivery\" on an entity for streaming/broker options.",
      ],
      glossary: ["rest_output", "websocket_output", "kafka_output"],
    },
  },
  {
    pattern: /^\/projects\/[^/]+\/monitor/,
    topic: {
      title: "Live monitor",
      what: "Rows per second, active streams, and error rates while a simulation is running.",
      actions: ["Nothing to configure here — this updates automatically while data is flowing."],
    },
  },
  {
    pattern: /^\/projects\/[^/]+\/governance/,
    topic: {
      title: "Governance",
      what: "Who changed what, saved versions of this project's design, and who else it's shared with.",
      actions: [
        "Save a version before a risky change, so you can roll back to it.",
        "Invite a teammate to share this project.",
      ],
    },
  },
  {
    pattern: /^\/projects\/[^/]+\/data/,
    topic: {
      title: "Data & jobs",
      what: "Generation jobs, schedules, saved record stores, and lookup tables for this project.",
      actions: [
        "Browse a record store to see what's actually been generated into it.",
        "Schedule a recurring generation job instead of clicking Generate by hand.",
      ],
    },
  },
  {
    pattern: /^\/projects\/[^/]+$/,
    topic: {
      title: "System map",
      what: "Your project's entities, how they relate, and where their data goes — laid out as a diagram.",
      actions: [
        "Click an entity to open and edit it.",
        "Switch to the list view if the canvas feels like more than you need.",
      ],
    },
  },
  {
    pattern: /^\/projects$/,
    topic: {
      title: "Projects",
      what: "A project is one system you're modelling — its entities, how they relate, and everywhere its data goes.",
      actions: [
        "Start from a starter template if you're not sure where to begin.",
        "Import a schema you already have (SQL, JSON Schema, or a sample file).",
      ],
    },
  },
  {
    pattern: /^\/settings\/api-keys/,
    topic: {
      title: "API keys",
      what: "Credentials for calling SynthFlow's own API from a script or another service, instead of signing in as a person.",
      actions: ["Create a key scoped to one project rather than your whole account, when you can."],
    },
  },
  {
    pattern: /^\/settings\/organizations/,
    topic: {
      title: "Organizations",
      what: "Shared workspaces — projects owned by a team instead of one person, with roles controlling who can do what.",
      actions: ["Invite a teammate, or move a personal project into a shared organization."],
    },
  },
  {
    pattern: /^\/settings\/activity/,
    topic: {
      title: "Activity",
      what: "An audit log of who changed what, across every project you can see.",
      actions: [],
    },
  },
];

export function helpTopicFor(pathname: string): HelpTopic | null {
  return TOPICS.find((t) => t.pattern.test(pathname))?.topic ?? null;
}

export function allHelpTopics(): HelpTopic[] {
  return TOPICS.map((t) => t.topic);
}
