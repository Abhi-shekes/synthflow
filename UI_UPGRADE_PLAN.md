# UI Upgrade Plan

A plan to take the frontend from "a working form over the API" to an
instrument panel for a running system — and to surface the backend
features that shipped without a UI.

This is a frontend-only track. It adds one backend endpoint (a metrics
summary, §4.2) and otherwise consumes what already exists.

---

## 1. Where the frontend actually is

Numbers first, because the shape of the problem is in them.

| | |
|---|---|
| Frontend source | 11,484 lines across 49 files |
| The two pages that *are* the product | 957 and **1,655** lines |
| Cards stacked on the entity page | **16**, all identical weight |
| Responsive utility classes in the whole app | **8** |
| Links in the whole app | 9 |
| Theme | untouched shadcn default; `--chart-1..5` are all zero-chroma grey |
| `next-themes` | installed, never imported. No dark mode exists. |
| Animation / chart / canvas libraries | none |

### 1.1 The README describes a UI that was never built

`README.md` lists React Flow, Recharts, and Monaco Editor in the tech
stack table. **None of the three are in `frontend/package.json`.** Four
headline features are therefore claims without a surface:

- *"Visual schema builder"* — is a `<Table>` of field rows.
- *"Relationship builder"* — is a `<Select>` pair inside a dialog.
- *"Workflow / state machine builder — visual state machines"* — is
  `add-workflow-dialog.tsx`, where you type states as
  `created, packed, shipped, delivered` into one `<Input>` and
  transitions as `source>target` strings into another. There is no
  diagram anywhere in the product.
- *"Live monitoring — events/sec, active streams, resource usage,
  error rates"* — exists only in Grafana, behind an optional Compose
  profile. The app itself shows none of it.

Fix the README or fix the UI. This plan fixes the UI.

### 1.2 The structural problem: two monster pages

`app/projects/[projectId]/entities/[entityId]/page.tsx` is a flat
vertical stack of sixteen `<Card>`s:

> Fields · Rules · Event triggers · Workflows · Trends · Error injection ·
> Lookups · Geo routes · REST output · Live stream (WebSocket) · Kafka ·
> RabbitMQ · Signed webhook · MQTT · Plugin output · Generate

Every one renders at `CardTitle className="text-base"`. Nothing is
grouped, nothing is prioritised, nothing is collapsed, and "Generate" —
the reason you came — is at the bottom of 1,600 lines. You configure a
trend, scroll past nine cards, click Generate, and scroll back up to see
whether you got what you wanted. The feedback loop is the core defect,
and no amount of restyling fixes it. §3.2 rebuilds this page.

`app/projects/[projectId]/page.tsx` has the same disease at 10 cards.

### 1.3 What is genuinely fine

Worth saying, so the rebuild doesn't throw it away: `lib/api.ts` (1,187
lines, 138 operations) and `lib/types.ts` (1,021 lines) are complete,
consistent, and well-typed. TanStack Query usage is correct, including
the conditional 1s poll on active jobs in `jobs-card.tsx`. The dialog
components are reasonable. **The data layer stays. The presentation
layer is what gets replaced.**

---

## 2. Design direction

The trap here is reaching for the current default — glass panels, a
gradient hero, a purple-to-blue button — which reads as templated
precisely because everyone reaches for it. The direction below comes
from what this product *is* instead.

SynthFlow's claim is that its data **behaves**: entities hold state,
relationships hold together, rules fire, streams flow to destinations.
So the interface should be a view over a running system, not a form over
a database. Three ideas carry that, and they are the parts of this plan
that are not common.

### 2.1 Field type as colour — the one system that ties it together

There are 11 field types (`FieldType`) and three preset families
(`LogPreset`, `IdentifierPreset`, `PiiPreset`). Assign each type a
categorical hue and then use that *same* scale in every surface where a
field appears:

- the core-sample bands on entity nodes (§2.2)
- the field table
- generated-data table headers and the live specimen
- the schema-import diff
- the quality and privacy reports

This is the cheapest change with the largest effect on whether a
screenshot looks designed or assembled, and it does real work: you learn
to read an entity's shape by colour. PII presets get a distinct
treatment (a hatched overlay rather than a hue) because "this column is
personal data" is a different axis from "this column is a string".

The existing `--chart-1` … `--chart-5` are all grey and must be replaced
outright. Build the scale against the `dataviz` skill's palette rules
so it survives light and dark and passes contrast.

### 2.2 The System Map — the project page becomes a spatial canvas

Replace the 10-card project page with one pan/zoom canvas showing the
project as the pipeline it is, left to right:

```
   SOURCES                    ENTITIES                  DESTINATIONS
   ┌──────────┐                                          ┌──────────┐
   │ sample   │──┐         ┌──────────┐                ┌─│ REST     │
   │ file     │  │      ┌──│ Customer │──┐             │ ├──────────┤
   ├──────────┤  ├─────►│  ▓▓▒▒░░▓▒   │  │ 1:N         ├─│ Kafka    │
   │ postgres │──┤      └──────────┘  ▼                │ ├──────────┤
   ├──────────┤  │         ┌──────────┐                ├─│ S3       │
   │ S3 bucket│──┘         │ Order    │────────────────┘ ├──────────┤
   └──────────┘            │ ▓▓░░▒▒▓  │                  │ webhook  │
                           └──────────┘                  └──────────┘
```

- **Entity nodes are not titled rectangles.** Each is a **core sample**:
  a vertical stack of thin bands, one per field, coloured by field type
  (§2.1). You read an entity's composition from across the screen —
  mostly-string, mostly-numeric, has-a-PII-band — without reading a word.
  This is the distinctive move, and it is honest: the picture is
  generated from the schema, not decoration.
- **Level of detail on zoom.** Far: name and core sample only. Mid: add
  field-type counts and row totals. Near: the full field list inline,
  editable. One surface serves overview and editing, so there is no
  "open the entity to see anything" round trip.
- **Real depth, three z-planes.** A `perspective` on the canvas with
  grid backdrop, edges, and nodes on separate `translateZ` planes.
  Panning parallaxes them. This is actual 3D transform, not a bevel or a
  drop shadow pretending to be one — and it is doing a job (separating
  structure from content), which is the test any 3D effect has to pass
  to stay in.
- **Edges carry traffic.** When a WebSocket stream is live or a job is
  running, the relevant edges animate a dash offset at a rate driven by
  real throughput. A pipeline that is running should *look* running.
- **The Destinations band is free.** `GET /projects/{id}/outputs`
  already returns exactly this aggregate — every REST, WebSocket, Kafka,
  MQTT, RabbitMQ, webhook, plugin, database and replay output in one
  typed list. `api.listOutputs` exists in `lib/api.ts` and **nothing in
  the app calls it** (§4.7).

Build the canvas on `@xyflow/react`. Hand-rolling pan/zoom, edge
routing, and a minimap is two weeks we should not spend, and React Flow
was the intended dependency in the README anyway.

### 2.3 The Strata Inspector — the entity page becomes one scroll surface

The sixteen cards collapse into four **strata**, ordered the way data
actually moves through the engine:

| Stratum | What lives there |
|---|---|
| **Shape** | fields, types, presets, null rates, formulas |
| **Behaviour** | rules, event triggers, workflows, trends, lookups, geo routes |
| **Distortion** | error injection |
| **Delivery** | REST, WebSocket, Kafka, RabbitMQ, webhook, MQTT, plugin |

Two mechanics make it work:

**A sticky depth rail.** As you scroll, the current stratum's label
docks to the left edge and the ones you have passed compress to a 3px
coloured band. You always know how deep you are and can jump. This is
native CSS `animation-timeline: view()` — no GSAP, no Lenis, no scroll
library, no scroll-jacking.

**A pinned live specimen.** Five generated rows, always visible, in the
right third of the screen, regenerating as you edit. Change a trend, see
it. Add a rule, watch rows that violate it disappear. **This is the
single largest UX gain in the plan** and it is what kills the
scroll-down-scroll-back loop from §1.2.

And one scroll effect that earns its place rather than decorating: as
you scroll into the **Distortion** stratum, the specimen rows visibly
degrade in step with the scroll — nulls appear, values corrupt, ordering
breaks. Scrolling *is* the demonstration of what error injection does.
That is a scroll effect doing explanatory work, which is the only kind
worth building into a configuration tool.

### 2.4 Motion and 3D budget

Stated as a budget on purpose, because "modern with 3D and scroll
effects" becomes a toy without one. Inside the tool, **motion must be
informational**; decoration gets exactly one room.

| Where | What | Why it's allowed |
|---|---|---|
| System Map | z-plane parallax, animated traffic edges | conveys structure and live throughput |
| Entity nodes / cards | pointer-driven tilt, **≤6°** | affordance; capped so it reads as material, not a gimmick |
| Strata rail | scroll-linked dock/compress | conveys position |
| Specimen | scroll-linked degradation | explains the feature |
| Landing page (logged out) | one WebGL particle field — records flowing through transform nodes | the one place a "wow" belongs |

Everything is behind `prefers-reduced-motion`, and the reduced path is a
real static design, not the animation frozen at frame 0. No scroll-jacking
anywhere — hijacking scroll in a config-heavy tool is actively hostile.

### 2.5 Shell, theme, typography

- **Dark-first.** This is an operator's instrument, not a marketing site.
  Near-black base, one saturated accent, plus the categorical field
  scale. Light theme is a real second design, not an inversion.
  Actually wire `next-themes` — it is already a dependency (§1) — with a
  visible toggle.
- **Persistent left rail** replacing the flat header: Projects · Map ·
  Entities · Data · Delivery · Jobs · Governance. Plus breadcrumbs,
  which do not exist today.
- **Command palette (⌘K)** over projects, entities, fields, outputs and
  actions. With 138 API operations, search is the only navigation that
  scales, and it is what turns a large surface into a fast one.
- **Typography off the default.** Geist for everything is the giveaway
  of an untouched scaffold. A distinct display face for headings and
  numerics, and a mono with real tabular figures for the data tables and
  stream preview — those tables are half the product.
- **Responsiveness**, since there is effectively none (§1). The System
  Map degrades to a list below `md`; the Strata Inspector drops the
  pinned specimen to a bottom sheet.

---

## 3. Feature gaps: backend shipped, frontend missing

Found by diffing every route in `backend/app/api/routes/` against every
call site in `frontend/`. Ordered by user impact.

### 3.1 Privacy and anonymity report — no UI at all
`POST /projects/{id}/entities/{id}/privacy-report` measures k-anonymity
and l-diversity on generated output and returns `passes: true|false`.
There is **no `privacyReport` method in `lib/api.ts`** and no component
references it. Phase 10 is described at length in the README and is
entirely invisible in the product. Needs a client method, a types entry,
and a panel — most naturally next to the existing quality report.

### 3.2 In-app live monitoring — no UI at all
The README promises events/sec, active streams, resource usage and error
rates. `/metrics` is Prometheus text, deliberately unauthenticated and
outside `/api/v1`. Nothing in the frontend reads it. **This is the one
item needing backend work:** add `GET /api/v1/metrics/summary` returning
a small authenticated JSON projection of the same gauges, rather than
parsing exposition format in the browser or exposing the raw endpoint to
the app's origin.

### 3.3 Nothing can be edited
`PATCH /entities/{entity_id}` and
`PATCH /entities/{entity_id}/fields/{field_id}` both exist and are
implemented. **The frontend has no edit path whatsoever** — and no
client method for either. Entities and fields are create-and-delete
only. You cannot rename an entity, change a field's type, or adjust a
null rate without deleting and rebuilding. For a schema design tool this
is the most damaging gap on the list.

### 3.4 An entity cannot be deleted
`api.deleteEntity` exists in `lib/api.ts` and **no button anywhere calls
it**. The backend route is live. This is a missing `onClick`.

### 3.5 Schema import from a live database is unreachable
`api.importSchemaFromDatabase` exists; nothing calls it.
`schema-import-dialog.tsx` reaches SQL, JSON Schema, and sample-file
import, but not the database path — despite it being the headline of
Phase 7.

### 3.6 Record stores cannot be browsed
`GET /record-stores/{id}/records` and `api.listStoredRecords` exist,
unused. `record-stores-card.tsx` can generate into a store, backfill it,
and read its change log — but you cannot look at what is actually in it.

### 3.7 No aggregate outputs view
`GET /projects/{id}/outputs` returns every output across nine types as
one typed list. `api.listOutputs` is unused. Today, answering "where
does this project's data go?" means opening each entity and scrolling
seven cards. This is also the exact feed for §2.2's Destinations band.

### 3.8 Smaller ones
- `api.deleteProjectVersion` — unused; versions accumulate with no prune.
- `api.jobArtifactUrl` — unused; artifacts only reachable via blob download.
- Audit log is project-scoped only (`activity-card.tsx`); there is no
  org-wide view, though `listAuditEvents` supports it.
- SSO status is read at login, but there is no admin surface for OIDC
  configuration.

### 3.9 Dead code to delete
Superseded by the nested payload from `getEntity`, which already returns
these relations inline: `listRules`, `listEventTriggers`, `listWorkflows`,
`listTrends`, `listErrorInjections`, `listLookupAttachments`,
`listGeoRoutes`. Seven unused client methods.

---

## 4. Phasing

Sequenced so the redesign is never built on top of missing capability —
**U2 before U3 and U4** is the load-bearing ordering decision here.
Rebuilding the entity page first and then discovering it needs an edit
path means building that page twice.

### U1 — Foundation *(no new screens)*
Design tokens and the dark-first palette. The field-type colour scale
(§2.1) replacing the grey `--chart-*`. Typography. A real theme toggle
wired to the already-installed `next-themes`. The app shell: left rail,
breadcrumbs, ⌘K palette. Motion primitives and the `prefers-reduced-motion`
path. Responsive baseline.
*Nothing user-visible changes structurally; everything after this gets cheaper.*

### U2 — Close the gaps
Every item in §3. Edit entity and field, delete entity, privacy report
panel, record browser, outputs aggregate, database schema import, version
delete, artifact links, the `/metrics/summary` endpoint. Delete §3.9's
dead code.
*Pure capability, zero redesign risk. Ship independently.*

### U3 — Strata Inspector
Rebuild the 1,655-line entity page per §2.3. Sticky depth rail, pinned
live specimen, scroll-linked distortion preview.
*The largest single UX gain. Highest priority of the three redesigns.*

### U4 — System Map
Rebuild the project page as the canvas in §2.2. React Flow, core-sample
nodes, z-plane parallax, LOD on zoom, Destinations band fed by §3.7.

### U5 — Live surfaces and landing
In-app monitoring dashboard on §3.2. Traffic-driven edge animation on the
map. The WebGL landing page. Charts throughout (Recharts, finally
installed) for trends, quality, and throughput.

---

## 5. Dependencies to add

| Package | For | Note |
|---|---|---|
| `@xyflow/react` | System Map | the README's React Flow, at last |
| `recharts` | trends, quality, monitoring | ditto |
| `motion` | orchestration only | scroll work stays native CSS |
| `cmdk` | ⌘K palette | |
| `three` | landing page only | **U5 only**, route-split — verified isolated in its own 520 KB chunk, referenced by `app/page` alone. `@react-three/fiber` not needed for a single `Points` system. |

`next-themes` needs no install — it is already a dependency and simply
unused (§1).

---

## 6. Tradeoffs recorded

Written down rather than left implicit, in the style of `ROADMAP.md`.

- **React Flow over a hand-rolled canvas.** ~50kb gzipped against two
  weeks of pan/zoom, edge routing, and minimap work we would maintain
  forever. Taken.
- **Native CSS scroll-driven animation over a scroll library.** Zero
  bytes, no scroll-jacking, degrades to static in unsupporting browsers.
  Cost: `animation-timeline` needs a fallback path for Firefox and older
  Safari, and the fallback is "no scroll effect", not "broken layout".
- **The live specimen costs generate calls.** Every edit re-generates 5
  rows. Debounced, capped at 5 rows, and cancelled on unmount — but it
  is real backend load that the current design does not create. Worth
  it: the feedback loop is the product's main defect.
- **Dark-first means the light theme is second-class at first.** Accepted
  for U1; light reaches parity by U3.
- **`/metrics/summary` duplicates a projection of the Prometheus
  gauges.** Two surfaces over one set of numbers. The alternative —
  parsing exposition format in the browser, or exposing the
  unauthenticated `/metrics` to the app origin — is worse on both
  security and maintenance.
- **3D is capped at ≤6° tilt and three z-planes.** Deliberately austere.
  Every effect that survived has a job; the budget in §2.4 exists so the
  next person adding one has to argue for it.
