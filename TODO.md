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

## Now — Phase 3, part 2: REST output, plugin manager, DB connectors

- [ ] Output plugin manager: a per-project config of which output(s) are
      enabled, modeled so Phase 5's "install only REST" story is possible
      later without a rewrite (see Notes below). Don't build this as an empty
      shell of toggles for things that don't work yet — let it grow out of
      the DB-connector config below, which actually needs persisted
      per-project settings (host/port/credentials/table mapping).
- [ ] REST output: likely just documentation/framing rather than new code —
      `POST .../generate` already IS the REST output; decide if this item is
      "expose it as a stable read endpoint distinct from the generate action"
      or if it's already satisfied
- [ ] Database connectors: write generated rows into a real Postgres/MySQL/
      Mongo target the user configures (host, port, credentials, database,
      table-per-entity mapping), instead of just returning them. Needs: a
      "test connection" action, safe identifier handling (SQLAlchemy
      quoting, never raw string interpolation into DDL/DML), and a
      write-only password field (never echoed back in API responses — this
      repo doesn't have secret encryption-at-rest yet, so say so plainly in
      the UI rather than implying more security than exists)
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
