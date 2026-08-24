export interface TourStep {
  id: string;
  /** CSS selector for the element to spotlight. `use-tour-target` resolves the
   * first *visible* match, so the same selector can exist twice in the DOM
   * (e.g. the desktop rail and the mobile phone-strip nav) without special-casing. */
  selector: string;
  title: string;
  body: string;
  /** "click" steps advance when the real target element is clicked — the
   * click performs its normal job (navigate, expand, toggle) and moves the
   * tour forward in the same gesture. "button" steps only advance via the
   * tooltip's own Next button, for steps that shouldn't force an action
   * (adding data, changing a setting) on someone's real project. */
  advance: "click" | "button";
}

/**
 * The tour never calls `router.push` itself. Every step that needs to be on a
 * different page is a "click" step whose target is a real navigation link
 * (a rail item, an entity card) — the app's own navigation moves the tour,
 * the same way a person would actually get there. This sidesteps an entire
 * class of bug: a programmatic push racing the app's own route-driven state
 * (see the `app-shell.tsx` `lastProjectId` effects) is exactly what caused
 * the "Maximum update depth exceeded" crash this tour replaces the old guide
 * because of.
 *
 * A step whose target never becomes visible (no entities yet, a stratum
 * that's already expanded, the live specimen panel hidden below `xl`) is
 * skipped automatically by `use-tour-target`'s timeout — there is no
 * separate `skipIf` to keep in sync with every place content can vary.
 */
export const STEPS: TourStep[] = [
  {
    id: "system-map",
    selector: '[data-tour="system-map-header"]',
    title: "This is your system map",
    body: "Every entity, how they relate to each other, and where their data goes — all in one place.",
    advance: "button",
  },
  {
    id: "add-entity",
    selector: '[data-tour="add-entity"]',
    title: "Add an entity",
    body: "Type a name and hit Add — it appears on the map immediately, and its bands fill in as you add fields.",
    advance: "button",
  },
  {
    id: "open-entity",
    selector: '[data-tour="first-entity-card"]',
    title: "Click any entity",
    body: "Opens it for editing. Skipped automatically if this project doesn't have one yet.",
    advance: "click",
  },
  {
    id: "shape",
    selector: "#shape",
    title: "Shape",
    body: "The one layer every entity needs — fields, types, and how often each is null.",
    advance: "button",
  },
  {
    id: "fields",
    selector: '[data-tour="fields-panel"]',
    title: "Fields",
    body: "Add a field, set its type, and mark it required, unique, or nullable from here.",
    advance: "button",
  },
  {
    id: "specimen",
    selector: '[data-tour="specimen"]',
    title: "Live specimen",
    body: "Regenerates automatically as you edit — change a field and watch real sample rows update, without ever clicking Generate.",
    advance: "button",
  },
  {
    id: "behaviour",
    selector: '[data-tour="rail-behaviour"]',
    title: "Behaviour",
    body: "Rules, triggers, workflows, and trends — how values move and constrain each other. Click to jump there.",
    advance: "click",
  },
  {
    id: "add-behaviour",
    selector: '[data-tour="add-behaviour"]',
    title: "Add behaviour",
    body: "Click to expand — collapsed when empty so an empty layer doesn't take up space. Skipped if this entity already has some.",
    advance: "click",
  },
  {
    id: "distortion",
    selector: '[data-tour="rail-distortion"]',
    title: "Distortion",
    body: "Deliberately corrupts some rows so you can test how you handle bad data before it reaches you. Click to jump there.",
    advance: "click",
  },
  {
    id: "add-distortion",
    selector: '[data-tour="add-distortion"]',
    title: "Add distortion",
    body: "Same idea — click to expand. Skipped if this entity already has some configured.",
    advance: "click",
  },
  {
    id: "generate",
    selector: '[data-tour="generate-button"]',
    title: "Generate",
    body: "Click to produce rows on demand and see them in a table right here.",
    advance: "click",
  },
  {
    id: "generated-rows",
    selector: '[data-tour="generated-rows"]',
    title: "There they are",
    body: "This also feeds the Download CSV / Download Excel buttons next to Generate.",
    advance: "button",
  },
  {
    id: "mode-toggle",
    selector: 'button[aria-label="Advanced"]',
    title: "Guided vs. Advanced",
    body: "Click to flip — every layer expands, every delivery protocol shows at once, and the rail gains three more pages. Nothing is ever deleted or locked behind Guided; it's only what's visible by default.",
    advance: "click",
  },
  {
    id: "nav-data",
    selector: '[data-tour="nav-data-jobs"]',
    title: "Data & jobs",
    body: "Background jobs, schedules, record stores, and connections — everything about running generation rather than designing the schema. Click to open it.",
    advance: "click",
  },
  {
    id: "nav-delivery",
    selector: '[data-tour="nav-delivery"]',
    title: "Delivery",
    body: "Every output configured on every entity, in one read-only place. Click to open it.",
    advance: "click",
  },
  {
    id: "nav-monitor",
    selector: '[data-tour="nav-monitor"]',
    title: "Live monitor",
    body: "Rows per second, active streams, and error rates for the whole running system — not scoped to one project. Click to open it.",
    advance: "click",
  },
  {
    id: "nav-governance",
    selector: '[data-tour="nav-governance"]',
    title: "Governance",
    body: "Sharing, version history, and an activity log of every change — the three controls you reach for when something's gone wrong. Click to open it.",
    advance: "click",
  },
  {
    id: "command-palette",
    selector: '[data-tour="command-palette-trigger"]',
    title: "Command palette",
    body: "Press ⌘K (Ctrl+K on Windows/Linux) anywhere to search projects, pages, entities, and fields by name.",
    advance: "button",
  },
  {
    id: "theme",
    selector: '[data-tour="theme-toggle"]',
    title: "Light and dark theme",
    body: "Dark by default, but light is a fully designed second theme, not an inverted afterthought. Switch any time.",
    advance: "button",
  },
  {
    // Navigate first, *then* open Help — not the other way round. Opening
    // Help renders a full-viewport backdrop (`fixed inset-0 z-40`) that sits
    // above the rail (z-30) and swallows the very next click before it can
    // reach the nav link underneath, so a step that needs to click a rail
    // link can never follow directly after one that opens the panel.
    id: "back-to-projects",
    selector: '[data-tour="nav-all-projects"]',
    title: "Every project, any time",
    body: "API keys, Organizations, and Activity live in this Workspace section too, reached the same way. Click here to head back.",
    advance: "click",
  },
  {
    // On /projects now, where the getting-started checklist (next step)
    // sits in the main content column, clear of this panel's right-side
    // slide-over — so leaving it open doesn't block what comes after it.
    id: "help",
    selector: 'button[aria-label="Help"]',
    title: "Get help without leaving the page",
    body: "A short explanation of what this page is for, plus definitions for any jargon on it. Click to open it.",
    advance: "click",
  },
  {
    id: "getting-started",
    selector: '[data-tour="getting-started"]',
    title: "You've seen the whole app",
    body: "This checklist ticks off automatically as you go and dismisses on its own once you're done. Replay this tour any time from the Help panel.",
    advance: "button",
  },
];
