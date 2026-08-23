# Simplicity & Onboarding Plan

A plan to make SynthFlow usable by someone who is not a data engineer, without
throwing away the instrument-panel redesign in `UI_UPGRADE_PLAN.md` (U1–U5,
all shipped). That track built a serious tool for a technical operator. This
track adds the layer underneath it: a way in for everyone else, help while
they're in it, and a first five minutes that teaches instead of dumping them
on an empty page.

This is additive, not a rewrite. Nothing here proposes removing the System
Map, the Strata Inspector, or any capability. It proposes a **Guided mode**
that hides depth by default, a **Helper layer** that explains what's on
screen, and an **onboarding flow** that exists at all — today there isn't one.

---

## 1. Why this is a real problem, not a vibe

The README lists the product's own feature surface: visual schema builder,
relationship builder, stateful entities, a workflow/state-machine builder,
rules engine, formula engine, trend/correlation/probability engines, event
triggers, error injection, timeline replay, domain simulators, digital twin
modeling, seven delivery protocols (REST, WebSocket, Kafka, RabbitMQ, MQTT,
webhook, plugin), k-anonymity/l-diversity privacy reports, orgs/roles/SSO,
audit logs, API keys. That's the pitch, and it's accurate — but it's also
~20 pieces of jargon a first-time, non-technical user has to clear before
they get one row of fake data out.

The U3 entity page already organizes this into four strata (Shape,
Behaviour, Distortion, Delivery) — a real improvement over sixteen flat
cards — but Behaviour alone still means rules, event triggers, workflows,
trends, lookups, and geo routes, all visible by default the moment you open
an entity. There is no mode where a new user only sees what they need for
"give me realistic fake data for my app."

**There is no onboarding at all.** `frontend/app/projects/page.tsx` sends a
first-time signup straight to a page whose only guidance is a
`PanelEmpty`: *"No projects yet. Create one from scratch, import a schema
you already have, or start from one of the templates below."* That's a
reasonable empty state — it's the entire onboarding experience. There's no
tour, no seeded example, no checklist, no explanation of what a "stratum" or
"k-anonymity" or "trend" means before you're expected to configure one.

And the visual language U1–U5 chose — deliberately: "dark-first... this is
an operator's instrument, not a marketing site" (`UI_UPGRADE_PLAN.md` §2.5)
— is correct for the audience it targeted and wrong for a first-time,
non-technical visitor. That's not a bug in U1–U5; it's a gap next to it.

## 2. Principle: progressive disclosure, one glossary, no forked pages

Three temptations to resist, because each one turns into a maintenance
burden:

- **Don't fork components into "simple" and "advanced" versions.** Every
  simplification is a *default state* (collapsed, hidden behind a toggle,
  reworded) on the same component, driven by one mode flag. Two copies of
  the Strata Inspector drift apart within two sprints.
- **Don't scatter plain-language copy inline.** One glossary module is the
  single source for every tooltip, empty state, and coach mark. Jargon gets
  explained once and referenced everywhere, the same discipline
  `lib/field-visual.ts` already applies to color.
- **Don't gate capability behind Guided mode — gate visibility.** A Guided
  user can always reach Advanced; nothing is deleted or locked, only
  deferred. This mirrors the U2 principle of the last track: "pure
  capability, zero redesign risk."

---

## 3. Track A — Guided mode (the design plan)

A mode flag (`viewMode: "guided" | "advanced"`), default **guided** for
every new account, stored per-user (account setting, not per-project — a
user's comfort level doesn't reset per project) and overridable any time
from the header. Advanced users flip it once and never see it again;
`localStorage` plus a synced account field so it survives across devices.

### A.1 — Navigation

- Guided rail: **Projects · This project · Generate · Delivery · Help.**
  `Data & jobs`, `Governance`, `Monitor`, `Organizations`, `API keys` collapse
  under a single "Advanced" rail entry rather than five permanent slots —
  they're still one click away, not removed.
- Command palette stays identical in both modes. Search is search; hiding it
  from a new user helps no one, and ⌘K is already opt-in by nature.

### A.2 — The entity page (Strata Inspector)

- **Shape** stays open by default in both modes — it's the one stratum
  every user needs.
- **Behaviour, Distortion, Delivery** collapse to a single summary row each
  in Guided mode: an icon, a plain-language one-liner ("Add rules like 'age
  must be 18+'"), and an "Add" affordance that expands it in place. This is
  the same stratum, same component, just collapsed — not a different page.
- **Delivery** in Guided mode surfaces two options up front — **Download a
  file** and **REST endpoint** — with Kafka/RabbitMQ/MQTT/WebSocket/plugin
  under an "Advanced delivery" expander. Most people asking for synthetic
  data want a CSV or a URL, not a broker.

### A.3 — The System Map

- Guided mode defaults to the **list view** that currently only exists as
  the sub-`md` fallback (U4). The canvas — z-planes, tilt, LOD-on-zoom — is
  a genuine "wow" for someone who already understands the pipeline shape;
  for someone who doesn't, it's one more thing to parse before they see
  their entities. One toggle switches to the canvas; nothing about the
  canvas itself changes.

### A.4 — Copy pass

- One `lib/glossary.ts`: `{ id, term, plain, example? }` for every jargon
  term — `k_anonymity`, `l_diversity`, `quasi_identifier`, `event_trigger`,
  `trend`, `geo_route`, `lookup_attachment`, `error_injection`, each
  delivery protocol, `formula`, `rule`. This is the data both the Helper
  layer (Track B) and Guided-mode labels read from, so a definition changes
  in one place.
- Stratum and panel labels stay as-is (`Shape`/`Behaviour`/`Distortion`/
  `Delivery` are already reasonably plain); the jargon that needs glossing
  lives one level down, inside each stratum.

---

## 4. Track B — the Helper layer

Every affordance here is a wrapper around `lib/glossary.ts`; none of it
needs new copy written twice.

### B.1 — Inline term help

- A small `<Term id="k_anonymity">` component: renders its label plus an
  info affordance (hover on desktop, tap on mobile) showing `plain` and, if
  present, `example`. Applied at every jargon site — field presets, the
  privacy report panel, trend configuration, delivery protocol pickers.

### B.2 — Context help panel

- A persistent "?" in the header opens a slide-over that reads the current
  route and shows: what this page is for in one paragraph, the 2–3 things
  people usually do here, and links to the relevant glossary entries. Static
  content keyed by route, not a chatbot — cheap, no backend dependency,
  ships in one phase.

### B.3 — Empty states, everywhere

- `PanelEmpty` on `/projects` already does this right: what it is, why you'd
  want it, a CTA. Every stratum section and every "no X yet" in the app
  should follow the same three-part shape instead of a bare "No rules yet."
  This is a copy-and-wiring pass, not new design.

### B.4 — Plain-language errors

- Backend validation errors currently surface as raw messages in `sonner`
  toasts (e.g. every `onError: (error) => toast.error(error.message)` in
  `projects/page.tsx`). A small error-translation map for the common,
  user-facing failure cases (bad regex, duplicate field name, invalid
  connection string) turns "422 Unprocessable Entity" into "That regex
  doesn't compile — check the pattern." Fall back to the raw message for
  anything unmapped; don't try to translate everything up front.

### B.5 — Ask-in-plain-English (stretch, depends on Phase 6)

- `ROADMAP.md` Phase 6 (BYO-LLM, prompt → schema/rules/workflow) is **not
  started** — `[ ]` throughout. B.5 is scoped separately and only makes
  sense once Phase 6 ships: an assistant that takes "customers must be over
  18" and proposes a rule for review, or explains what a specific
  configuration will do. Keep this out of the Helper layer's first release;
  track it as a Phase 6 dependency, not invent a second AI integration.

---

## 5. Track C — first-run onboarding

### C.1 — Welcome flow, once

- A `has_onboarded` flag on the user record. First login (not first
  *signup* — someone can sign up and come back later) routes through a
  3-step flow before `/projects`: **(1)** "What are you here for?" — quick
  sample data / model a real system / import an existing schema — purely to
  pick the starting template, not a hard fork of the product. **(2)** pick a
  starter template or "start blank." **(3)** land inside that project with
  the coach marks (C.3) armed for first visit to each major surface.
  Skippable at every step; skipping still sets the flag so it never
  re-triggers uninvited.

### C.2 — Seed, don't greet an empty page

- Every new account gets a populated project by the time the welcome flow
  finishes — reusing an existing starter template
  (`api.listStarterTemplates`/`useStarterTemplate`, already built for U2) —
  so `/projects` is never a cold `PanelEmpty` for a first-time user. Today's
  empty state is a fine *second* line of defense, not a fine *first*
  impression.
- **Implemented as part of the welcome flow's own actions, not an
  unconditional seed on `POST /auth/signup`.** An automatic backend seed
  was tried first and reverted: it broke five existing tests' assumption
  that a fresh signup starts with zero projects, and the same assumption is
  just as reasonable for anyone else calling the signup API directly (a
  script, an SDK, a future integration) — surprising all of them with an
  extra project they didn't ask for is worse than the empty-state fallback
  it was meant to avoid. Seeding only when someone actually goes through
  `/welcome` has no such blast radius.

### C.3 — Coach marks

- A short, one-time spotlight sequence on first visit to the System Map, the
  four strata on the entity page, and Delivery. Built on existing
  `Panel`/`tone` primitives — no new dependency, no scroll-jacking, respects
  `prefers-reduced-motion` per the existing motion budget
  (`UI_UPGRADE_PLAN.md` §2.4). Dismiss is permanent, tracked alongside
  `has_onboarded`.

### C.4 — Getting-started checklist

- A dismissible card on `/projects`, visible until complete or dismissed:
  create/open a project → add or import an entity → generate your first
  sample → (optional) connect a delivery target. Same pattern as GitHub's or
  Linear's onboarding checklist — a small, honest progress indicator, not a
  gate.

### C.5 — A "Learn" page

- One page translating the README's feature list into plain language with
  a one-line example each. This becomes the page the Help panel (B.2) and
  every glossary entry (A.4) link out to for "tell me more." Written once,
  referenced everywhere — same discipline as the rest of this plan.

---

## 6. Phasing

Lettered `S1`–`S5` so they don't collide with `ROADMAP.md`'s numbered phases
or `UI_UPGRADE_PLAN.md`'s `U1`–`U5`. See `SIMPLICITY_TODO.md` for the
checklist.

| Phase | What | Depends on |
|---|---|---|
| **S1** | Glossary module + `<Term>` component + plain-language copy pass | none |
| **S2** | Guided/Advanced mode flag, nav collapse, entity-page stratum collapse, System Map list-view default | S1 |
| **S3** | Context help panel, empty-state pass, error-translation map | S1 |
| **S4** | Onboarding: welcome flow, seeded project, coach marks, checklist | S1, S2 |
| **S5** | Learn page | S1, S3 |

`S1` is the load-bearing dependency for everything else — every later phase
reads from the glossary rather than writing its own copy. Ship it first and
alone; it's zero redesign risk, same as U2 was for the last track.

**Explicitly out of scope for this plan:** B.5 (AI helper), which waits on
`ROADMAP.md` Phase 6.

## 7. Tradeoffs recorded

- **One mode flag, not forked pages.** Slightly more conditional rendering
  in each component; avoids two Strata Inspectors drifting apart. Taken.
- **Guided hides, never locks.** Every advanced surface stays one click
  away. Costs a small amount of "protect the user from themselves"; buys
  trust — nothing in Guided mode is ever a dead end.
- **List view as the Guided default on the System Map**, not a simplified
  canvas. Reuses the existing sub-`md` fallback instead of building a third
  visual mode. The canvas remains one toggle away, not rebuilt.
- **No chatbot in the first release.** A static, route-keyed help panel
  ships in one phase with no backend or LLM dependency; a real assistant
  waits for Phase 6 rather than becoming a second, uncoordinated AI
  integration.
- **Per-user mode, not per-project.** A user's comfort level is a property
  of the person, not the project — switching projects shouldn't reset it.
