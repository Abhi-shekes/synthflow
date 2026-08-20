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

## Phase 2, part 1: relationships — done

Relationship model + CRUD, `generate_project()` (topological generation order,
foreign-key values drawn from the real target rows), and a relationship
builder UI. Verified end-to-end in a browser. Full checklist: ROADMAP.md
Phase 2. Known simplification: `many_to_many` is generated the same as
`one_to_many` (no join-table modeling yet).

## Phase 2, part 2: rules & formulas — done

- [x] Safe expression evaluator — restricted-AST, no `eval()`
      (`backend/app/services/expressions.py`); arithmetic, comparisons,
      boolean logic, ternary, and a small function whitelist (`abs`, `min`,
      `max`, `round`, `len`)
- [x] Formula fields: `EntityField.formula` computes a value from other fields
      on the same row (must reference fields with a lower `order`); validated
      at field create/update time and evaluated during generation
- [x] Rules engine: per-entity `Rule.condition` a generated row must satisfy;
      a failing row is discarded and regenerated (bounded retries); validated
      at rule-create time against dummy field values
- [x] Rules/formula UI on the entity page — formula input in the field dialog,
      a Rules card (add/list/delete)
- Verified end-to-end in a browser: `total = price * quantity` held across 15
  generated rows, and a `price > 10` rule filtered every row correctly.
- Known limitation: rules are **same-row only** — no cross-entity rules yet
  (e.g. "if this Order's customer has tier=gold, ..."). Event-style triggers
  ("temperature > 80 → fire alert", "if payment success → generate invoice")
  are a distinct spec feature (4.12 Event Triggers) and are not implemented —
  they imply publishing a side-effect, not just computing/filtering a row.
- Known limitation: a rule-rejected candidate row still consumes unique-value
  state (a popped foreign-key slot, a `seen` entry) even though it's
  discarded — strict rules can exhaust a small unique pool faster than
  `count` alone would require. Documented in generate_rows()'s docstring.

## Now — Phase 2, part 3: stateful entities

Deferred out of part 2 deliberately — needs its own design pass rather than
being squeezed in. Open question to resolve first: our generation model is
flat batches (each `generate` call produces N independent rows), but "state"
implies a row progressing over time (`created → packed → shipped`). Options:
(a) constrain a field's generated value to a state-machine's node set, which
is really just enum with graph metadata and doesn't need new generation
logic; (b) generate a *history* per row (a sequence of state transitions with
timestamps) — a bigger, more honest interpretation of "stateful," but a
different output shape than everything else produces today. Decide (a) vs
(b) before writing models/routes, not while writing them.

- [ ] Decide the state-machine data model (states + transitions on an entity
      or a field) based on the (a)/(b) call above
- [ ] Workflow / state machine builder UI — simple state-list +
      transition-list form to start, matching the relationship builder's
      level of polish; the React Flow visual canvas from the spec is later

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules (Phase 2, stretch — needs rules to see sibling
      entities' already-generated rows, not just the current row)
- [ ] Output plugin manager + REST/Kafka/MQTT outputs (Phase 3)
- [ ] Trend/correlation/probability engines (Phase 4)
- [ ] Error injection + timeline replay (Phase 4)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5).
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- `app/services/expressions.py` is now shared infrastructure — reuse it for
  anything else that needs a user-authored expression (event triggers,
  cross-entity rules) rather than writing a second evaluator.
