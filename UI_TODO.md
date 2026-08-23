# UI TODO

Working checklist for the frontend upgrade track. For the reasoning — why the
strata, why the core samples, what the motion budget is and what it costs — see
[UI_UPGRADE_PLAN.md](UI_UPGRADE_PLAN.md). This file is only what's done, in
flight, and next.

Phases are lettered `U1`–`U5` so they never collide with ROADMAP.md's numbered
backend phases; the two tracks are independent except for one endpoint (U2.1).

## Status at a glance

| Phase | What | State |
|---|---|---|
| **U1** | Foundation — tokens, type, theme, shell, ⌘K | **done** |
| **U2** | Close the gaps — backend shipped, UI missing | **done** |
| **U3** | Strata Inspector — rebuild the entity page | **done** |
| **U4** | System Map — rebuild the project page | **done** |
| **U5** | Live surfaces — monitor, charts, landing | **done** |

**Ordering constraint that matters: U2 lands before U3 and U4.** U3 is where
entity/field editing and the privacy panel get their home, and U4's destinations
column is fed by U2's outputs aggregate. Rebuilding either page first means
building it twice.

---

## U1 — Foundation — done

No new screens. Everything after this got cheaper.

- [x] Add dependencies: `@xyflow/react`, `recharts`, `cmdk`. (`next-themes` was
      already a dependency and simply unused.)
- [x] Rebuild `app/globals.css` as a two-layer token system — the SynthFlow
      palette proper (ground/surface/ink/line/brand), then the shadcn contract
      re-pointed at it, so every existing `components/ui/*` inherits the new
      palette without being rewritten.
- [x] Replace the all-grey `--chart-1..5` with the 11-hue field-type scale.
      Severity (`--sev-crit/warn/note/ok`) is a **separate axis** from the brand
      accent, so "this is critical" never competes with "this is emphasised".
- [x] Light and dark as two real designs on `:root` / `.dark`, driven by
      next-themes' class strategy.
- [x] Typography off the scaffold default: Bricolage Grotesque (display),
      Instrument Sans (UI), IBM Plex Mono (data, with tabular figures).
- [x] Wire `next-themes` in `app/providers.tsx`, dark by default.
- [x] `components/shell/theme-toggle.tsx` — three-state segmented control.
      A two-way toggle silently drops "system" and can strand a viewer on the
      wrong theme with no way back to following the OS.
- [x] `components/shell/command-palette.tsx` — ⌘K over projects, entities,
      **fields**, and actions. Fields matter: "which entity has `customer_id`?"
      was previously answerable only by opening every entity in turn.
- [x] Rebuild `components/app-shell.tsx` — left rail (project + workspace
      sections), breadcrumbs, phone strip, theme toggle, sign-out.
- [x] `components/ui/panel.tsx` — the surface primitive, with an explicit
      `tone`. Deliberately not `Card`: sixteen `Card`s at identical weight is
      what made everything look equally important.
- [x] `lib/field-visual.ts` — one colour system. PII renders as a **hatch, not a
      hue**, because "this is personal data" is a different axis from "this is a
      string" and collapsing them loses one of the two.
- [x] `lib/motion.ts` — `useTilt` (capped at 6°), `useDebounced`,
      `useScrollProgress`, `useReducedMotion`.
- [x] Motion primitives in CSS, each with a **static** reduced-motion fallback
      rather than the animation frozen at frame zero.
- [x] `npx tsc --noEmit` clean.

---

## U2 — Close the gaps — done

Every item here is capability the backend already has and the UI cannot reach.
Pure value, zero redesign risk — ships independently of U3–U5.

### U2.1 — The one backend addition — done

- [x] `app/services/metrics.py`: add `summary()`, reading values back out of the
      Prometheus registry so there is no second set of counters to drift.
- [x] `GET /api/v1/metrics/summary` (`summary_router`), authenticated, registered
      in `app/main.py`. Verified: both `/metrics` and `/api/v1/metrics/summary`
      appear in the OpenAPI schema; `summary()` returns live values across all
      seven generation sources.
- [x] Return cumulative totals plus `captured_at`, not rates. A rate needs two
      samples and a clock, the polling client has both, and deriving it there
      keeps the endpoint stateless across API replicas.
- [x] Backend tests. Added to `tests/test_metrics.py` rather than a new file —
      same subject, and the delta-not-absolute rule in its module docstring
      applies to these too. Five cases: auth required, every generation source
      present (derived from the registry, not hardcoded), counters move by
      exactly the rows generated, the projection matches the registry it reads,
      and `captured_at` is the server's clock. **688 passed, 5 skipped** across
      the full suite — no regressions.

### U2.2 — API client corrections

- [x] Add `privacyReport(token, projectId, entityId, body)` → `POST
      /entities/{id}/privacy-report`. **Currently absent from `lib/api.ts`
      entirely** — all of Phase 10 is unreachable from the browser.
- [x] Add `PrivacyReport` + `PrivacyReportRequest` to `lib/types.ts`, mirroring
      the endpoint's return shape (`k`, `k_threshold`, `k_passes`, `l`,
      `l_passes`, `groups`, `rows_below_k`, `unique_row_share`,
      `smallest_groups`, `summary`).
- [x] Add `updateEntity` → `PATCH /entities/{id}`.
- [x] Add `updateField` → `PATCH /entities/{id}/fields/{fieldId}`.
- [x] Add `metricsSummary(token)` → the new U2.1 endpoint, plus its type.
- [x] Fix `OutputSummary` in `lib/types.ts`: missing `"rabbitmq"` and
      `"webhook"`, both of which the backend already returns.
- [x] Fix `GeneratorPresetSummary.category`: backend returns `"pii"` as a fourth
      value; the union type has three.
- [x] Delete seven dead methods superseded by the nested `getEntity` payload —
      `listRules`, `listEventTriggers`, `listWorkflows`, `listTrends`,
      `listErrorInjections`, `listLookupAttachments`, `listGeoRoutes`.

### U2.3 — Reachable capability

- [x] **Delete an entity.** `api.deleteEntity` exists and no button calls it.
      Wire it with a confirm — this is a missing `onClick`, nothing more.
- [x] **Schema import from a live database.** `api.importSchemaFromDatabase`
      exists, unused. Add the fourth tab to `components/schema-import-dialog.tsx`
      alongside SQL / JSON Schema / sample.
- [x] **Record browser.** `GET /record-stores/{id}/records` +
      `api.listStoredRecords`, unused. Add a records tab to
      `components/record-stores-card.tsx` — today you can generate into a store
      and read its change log but never look at what is in it.
- [x] **Delete a project version.** `api.deleteProjectVersion`, unused. Add to
      `components/version-history-card.tsx`; versions currently accumulate with
      no prune.
- [x] **Job artifacts** — resolved by *deleting* `api.jobArtifactUrl`, not by
      wiring it. It returns a bare path, and the artifact route requires a
      bearer token, so anything using it as an `href` would 401. The blob
      download beside it was already the only correct way to fetch one from a
      browser, so the helper was dead code with a trap in it.
- [x] Organisation-wide activity view at `/settings/activity`.
      `api.listAuditEvents` already supports the unscoped call;
      `components/activity-card.tsx` only ever passes a `projectId`.

### U2.4 — New routes the shell already links to

The rail and ⌘K palette reference these; **they 404 until this part lands.**
Nothing shipping is broken, but the nav is deliberately ahead of the pages.

- [x] `/projects/[projectId]/data` — jobs, schedules, record stores, lookup
      tables, timeline replays. (Moves `JobsCard`, `RecordStoresCard`,
      lookup-table and replay sections off the two monster pages.)
- [x] `/projects/[projectId]/delivery` — the aggregate outputs view built on
      `GET /projects/{id}/outputs`. Answering "where does this project's data
      go?" currently means opening each entity and scrolling seven cards.
- [x] `/projects/[projectId]/monitor` — built for real in one pass rather than
      stubbed, since the endpoint and Recharts were both already in place.
- [x] `/projects/[projectId]/governance` — version history, activity, sharing.
      (Moves `VersionHistoryCard`, `ActivityCard`, `ShareProjectCard`.)
- [x] `/settings/activity` — the org-wide audit view from U2.3.

---

## U3 — Strata Inspector

Rebuild `app/projects/[projectId]/entities/[entityId]/page.tsx` — 1,655 lines,
sixteen cards at identical weight, with "Generate" at the bottom. **The largest
single UX gain in the plan.**

### U3.0 — Outcome

The entity page went **1,655 → 998 lines**, and the project page **957 → 367**.
The seven delivery output forms live in `components/strata/delivery-stratum.tsx`
(888 lines) instead of inline: two thirds of the old file was output plumbing
nobody touches while designing a schema. Extracted *after* the strata were in
place, so the split follows the structure rather than guessing at it.

### U3.1 — Structure

- [x] Four strata, ordered the way data moves through the engine:
      - **Shape** — fields, types, presets, null rates, formulas
      - **Behaviour** — rules, event triggers, workflows, trends, lookups, geo routes
      - **Distortion** — error injection
      - **Delivery** — REST, WebSocket, Kafka, RabbitMQ, webhook, MQTT, plugin
- [x] `components/strata/stratum.tsx` — one stratum section, `id`-anchored so
      ⌘K's `#field-<id>` deep links land.
- [x] `components/strata/depth-rail.tsx` — sticky rail; the current stratum docks
      and passed ones compress to a 3px band. Native CSS `animation-timeline:
      view()`, already scaffolded as `.sf-rail-fill`. **No scroll library, no
      scroll-jacking** — hijacking scroll in a config-heavy tool is hostile.
- [x] Fallback check: Firefox / older Safari get a plain sticky rail. The
      degraded state is "no scroll effect", never "broken layout".

### U3.2 — The live specimen

- [x] `components/strata/specimen.tsx` — 5 generated rows pinned in the right
      third, regenerating as you edit. Change a trend and see it; add a rule and
      watch violating rows vanish. This is what kills the
      configure → scroll past nine cards → generate → scroll back loop.
- [x] Debounce via `useDebounced` (already built), cap at 5 rows, cancel in
      flight on unmount. **Recorded cost:** this is real backend load the current
      design does not create.
- [x] Below `md`, the specimen drops to a bottom sheet.
- [x] Column headers coloured by field type, from `lib/field-visual.ts`.

### U3.3 — The one scroll effect that earns its place

- [x] Scrolling into **Distortion** degrades the specimen in step with scroll
      progress — nulls appear, values corrupt, ordering breaks. The scroll *is*
      the demonstration of what error injection does.
- [x] Drive it from `useScrollProgress` (built), not a CSS timeline: the value
      has to reach React state to pick *which* rows to damage.
- [x] Under reduced motion, show the fully-injected sample statically.

### U3.4 — Editing, at last

- [x] Inline field edit — name, type, required/nullable/unique, null rate,
      min/max, regex, preset, enum values/weights, formula. Uses U2.2's
      `updateField`.
- [x] Rename entity, using `updateEntity`.
- [x] Delete entity (U2.3), from the entity header.
- [x] Field reordering, writing `order` through `updateField`.

### U3.5 — Panels that move here

- [x] `QualityReportDialog` → a Shape-stratum panel rather than a dialog.
- [x] **Privacy report panel** — the U2.2 client method's home. Quasi-identifier
      multi-select over the entity's own field names, sensitive-field picker, k
      and l thresholds, then a pass/fail readout with the smallest groups
      listed. Currently the single largest invisible feature in the product.
- [x] `RecordStoresCard` moves to `/data` (U2.4); the entity page keeps a link.

---

## U4 — System Map

Rebuild `app/projects/[projectId]/page.tsx` — 957 lines, ten cards — as one
pan/zoom canvas.

- [x] `components/map/system-map.tsx` on `@xyflow/react`, laid out the way the
      pipeline runs: **sources → entities → destinations**.
- [x] `components/map/core-sample-node.tsx` — an entity as a stack of thin bands,
      one per field, coloured by type, PII hatched. The distinctive move: you
      read an entity's composition from across the room, and the picture is
      generated from the schema so it can never go stale.
- [x] Relationship edges from `listRelationships`, labelled by type and
      cardinality.
- [x] Destinations column from `GET /projects/{id}/outputs` (U2.2's type fix
      lands first — the endpoint returns two kinds the frontend type omits).
- [x] Sources column: sample files, database connections, storage targets,
      schema import.
- [x] **Level of detail on zoom** — far: name + core sample; mid: type counts and
      row totals; near: full field list, editable in place. One surface serves
      overview and editing, so there's no round trip to see anything.
- [x] **Three z-planes** (grid backdrop / edges / nodes) under a real
      `perspective`, so panning parallaxes them. Genuine 3D transform doing a
      job — separating structure from content — not a bevel.
- [x] `useTilt` on nodes, capped at the budgeted 6°.
- [x] Below `md`, degrade to a plain list. A canvas on a phone is not a canvas.
- [x] Keyboard path: the canvas must not be the only way to reach an entity.
- [x] Sections that leave this page: jobs/lookups/replays → `/data`,
      versions/activity/sharing → `/governance`, outputs → `/delivery`.

---

## U5 — Live surfaces

- [x] `/projects/[projectId]/monitor` against U2.1's endpoint — rows/sec by
      source, active streams, active producers, error rates, generation latency,
      process CPU/memory.
- [x] Derive rates client-side from consecutive `captured_at` samples; hold a
      short ring buffer for sparklines. Poll on an interval, and **stop polling
      when the tab is hidden**.
- [x] Recharts throughout — trends (Behaviour stratum), quality report
      distributions, monitor sparklines. Load the `dataviz` skill's palette rules
      before choosing any chart colour; the field-type scale is already the
      categorical answer.
- [x] Traffic-driven edge animation on the System Map — `.sf-flow` exists and
      reads `--sf-dash-duration`; wire it to real throughput so a busier edge
      visibly moves faster.
- [x] Rebuild `app/page.tsx` (logged out) with one WebGL particle field —
      2,400 records flowing left→right along five lanes, coloured from the
      field-type scale. Written on `three` with a custom shader pair: position
      is a pure function of `uTime`, so the CPU uploads nothing after the first
      frame and the particle count costs nothing per frame.
      **Route-split and verified**, not assumed: `three` lands in one isolated
      520 KB chunk, and `react-loadable-manifest.json` lists it under
      `app/page` alone — no other route, and no shared bundle, references it.
      Handles a refused WebGL context, context loss/restore, and disposes every
      buffer and program on unmount (GPU memory is not garbage collected).
- [x] Restyle `app/login/page.tsx` and `app/signup/page.tsx` to the new system;
      keep the existing SSO branch (`api.ssoStatus`) intact.
- [x] Replace `components/stream-preview.tsx`'s `<ul>` of truncated strings with
      a real flowing tape of rows.

---

## Acceptance checks, every phase

- [x] `npx tsc --noEmit` and `npm run lint` clean.
- [x] `npm run build` succeeds.
- [x] Both themes checked on every new surface — including the un-stamped
      "system" state, not just the two explicit ones.
- [x] `prefers-reduced-motion` gives a **static design**, not a frozen animation.
- [x] Keyboard reachable, visible focus everywhere.
- [x] Usable at 375px. The old UI had **8 responsive utility classes in total**,
      so there is no existing baseline to preserve — this is new ground on every
      page.
- [x] Verified in a browser, not only by typecheck — matching the repo's habit
      of proving each phase end to end.

---

## Notes for future me

- **The data layer survives this whole track.** `lib/api.ts` (1,187 lines, 138
  operations) and `lib/types.ts` are complete and correctly typed; the TanStack
  Query usage is sound, including the conditional 1s poll on active jobs. Only
  the presentation layer is being replaced. Resist rewriting the client.
- **The README still lists React Flow, Recharts and Monaco as though they ship.**
  Two of the three become true in U4/U5. Monaco does not — formula and rule
  editing stays plain inputs unless something forces the question. Update the
  tech-stack table when U5 lands rather than leaving it aspirational.
- **`--chart-1..5` are now the field-type scale.** Anything reaching for a
  "chart colour" gets a field-type hue by default, which is correct when the
  series *is* a field and wrong otherwise. Pick explicitly for non-field series.
- **The motion budget is a budget.** Five places, listed in UI_UPGRADE_PLAN.md
  §2.4. Adding a sixth means arguing for it, which is the point of writing it
  down.
- **PII is a hatch, not a hue** — `lib/field-visual.ts`. Any new surface showing
  fields should go through `fieldFill()` rather than reading
  `FIELD_TYPE_COLOR` directly, or it will silently lose the sensitivity axis.
