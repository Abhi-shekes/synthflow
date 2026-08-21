# TODO

Active task list. This is the working checklist — for the phased overview see
[ROADMAP.md](ROADMAP.md). Keep this file short: only what's in flight or next up.

## Repo bootstrap (not blocking, pick up anytime)

- [x] Initialize repo, README, ROADMAP, LICENSE
- [ ] Add `.github/ISSUE_TEMPLATE` (bug report, feature request)
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Set up CI: lint + typecheck on push (GitHub Actions)
- [ ] Add branch protection on `main` once CI exists

## Phase 1 — done

Backend (auth, projects, entities/fields, generation engine, CSV export) and
frontend (auth pages, project/entity UI, schema builder v1, generate + CSV
download) are both live and wired together via `docker-compose.yml`. Full
checklist: ROADMAP.md Phase 1.

## Phase 2 — done (relationships, rules, formulas, stateful entities)

All four land on `app/services/expressions.py`, a shared safe restricted-AST
evaluator (no `eval()`). Full checklist: ROADMAP.md Phase 2. Verified
end-to-end in a browser for each. Known simplifications, carried forward:

- `many_to_many` relationships generate like `one_to_many` (no join-table yet)
- Rules and formulas are **same-row only** — no cross-entity rules
  (e.g. "if this Order's customer has tier=gold, ...")
- Event-style triggers ("temp > 80 → fire alert") are a distinct spec feature
  (4.12) and are NOT implemented — they publish a side-effect, they don't
  compute/filter a row, so they don't fit this engine as-is
- A rule-rejected candidate row still consumes unique-value state (a popped
  FK slot, a `seen` entry) even though it's discarded — strict rules can
  exhaust a small unique pool faster than `count` alone would require
- Stateful entities are a bounded random walk per row over a `Workflow`
  (states + initial states + transitions attached to one field), not a
  cross-call persistent state machine — there's still no notion of "the same
  record" between two `generate` calls, so "advance this order to the next
  state" isn't a thing yet. The walk is exposed as `<field>_history`.
- Only one leftover Phase 2 item: generated-field/auto-increment field
  support (see Backlog) — small, not blocking Phase 3.

## Phase 3, part 1: file outputs — done

- [x] Excel export, single-entity (`?format=xlsx` on `/entities/{id}/generate`,
      alongside the existing `?format=csv`)
- [x] Excel export, project-level: one workbook, one sheet per entity
- [x] CSV export, project-level: a zip of one `<entity>.csv` per entity (CSV
      has no multi-table concept, so no single-file project-wide CSV exists)
- [x] "Download CSV" / "Download Excel" buttons on both the entity page and
      the project's "Generate all entities" view
- Verified end-to-end in a browser against the full docker-compose stack:
  downloaded and inspected all three (entity .xlsx, project .zip, project
  .xlsx) — correct filenames, correct per-entity sheets/files, row counts
  matched the requested count.
- Design choice: Excel includes extra generation-time columns (e.g. a
  workflow field's `<field>_history`) that CSV drops — CSV is the strict
  fixed-column format, Excel isn't, so this isn't an inconsistency to fix
  later, it's intentional.

## Phase 3, part 2: database connectors — done

- [x] `DatabaseConnection` model (project-scoped): name, dialect, host, port,
      database, username, password (write-only — never returned by the read
      API; stored unencrypted, documented plainly in both the model
      docstring and the UI rather than implying more security than exists)
- [x] Test-connection action (`POST .../test`) and push action
      (`POST .../push`: generate N rows for one entity, respecting its rules
      and workflows, then create-if-not-exists the target table and insert)
- [x] Safe by construction, not by validation alone: table/column definitions
      go through SQLAlchemy Core `Table`/`Column` and parameterized
      `insert()` — never string-formatted SQL — with identifier names
      additionally checked against a strict `^[A-Za-z_][A-Za-z0-9_]{0,62}$`
      pattern so a bad name fails fast with a clear message
- [x] Scoped to PostgreSQL for v1 — matches the driver already vendored for
      the app's own control-plane DB. MySQL is modeled (`DatabaseDialect`)
      for forward-compat but `push`/`test` reject it with a clear 400 until
      that driver is added. MongoDB isn't modeled at all yet — its
      table/document paradigm doesn't map onto this Core-table approach, so
      it needs its own path, not a third branch bolted onto this one.
- [x] Frontend: a Database Connections card on the project page (add/test/
      delete) plus a push form (connection + entity + count)
- Verified for real, not just via the app's own tests: spun up a *separate*
  throwaway Postgres container on the same docker network (simulating a
  genuinely external database), added the connection through the UI, tested
  it, pushed 12 rows, and independently queried that external Postgres
  directly (`psql`) to confirm the table and rows actually landed there —
  not just that the UI showed a success toast.
- The backend test suite includes real push/create-table/idempotent-create
  tests too, but they're skip-guarded behind `TEST_EXTERNAL_PG_URL` so normal
  `pytest` runs don't depend on a live external Postgres being reachable.
- Bug found and fixed along the way (affects more than this feature): Base
  UI's `Select.Value` falls back to stringifying the raw `value` when it has
  no `items` map to resolve a label from — every `<Select>` in this app whose
  value is an id (not the same string as its label) was showing raw UUIDs
  once closed, not just the new database-connection pickers. Fixed by giving
  `SelectValue` a function-`children` label lookup in
  `add-relationship-dialog.tsx`, `add-workflow-dialog.tsx`, and the project
  page's push form. This had been shipping unnoticed because verification
  up to now only ever checked the *result* of a selection (the created
  relationship/workflow), never a screenshot of the closed dropdown itself.

## Now — Phase 3, part 3: REST output + plugin manager

- [ ] REST output: likely just documentation/framing rather than new code —
      `POST .../generate` already IS the REST output; decide if this item is
      "expose it as a stable read endpoint distinct from the generate action"
      or if it's already satisfied
- [ ] Output plugin manager: a per-project config of which output(s) are
      enabled, modeled so Phase 5's "install only REST" story is possible
      later without a rewrite. `DatabaseConnection` is the first real
      instance of "persisted per-project output config" — look at whether a
      plugin manager should generalize that model (one `Output` table with a
      polymorphic config blob) or stay as separate typed tables per output
      kind before building it, don't just default to one shape
- [ ] Streaming outputs (Kafka, MQTT, WebSocket) — biggest lift, needs the
      async execution model called out below; do this last in the phase

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules (Phase 2, stretch — needs rules to see sibling
      entities' already-generated rows, not just the current row)
- [ ] Trend/correlation/probability engines (Phase 4)
- [ ] Error injection + timeline replay (Phase 4)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5). This is now directly relevant: Phase 3 outputs are
  exactly the kind of thing that needs to be added/removed per-deployment later.
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- `app/services/expressions.py` is shared infrastructure — reuse it for anything
  else that needs a user-authored expression (event triggers, cross-entity rules)
  rather than writing a second evaluator.
- Generation is still fully synchronous request/response (`generate` returns
  rows directly). Streaming outputs (Kafka/MQTT/WebSocket) will need a real
  background/async execution model — don't try to bolt that onto the current
  request-handler shape; it's a different architecture, worth its own design
  pass like stateful entities got.
