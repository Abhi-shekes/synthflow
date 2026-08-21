# TODO

Active task list. This is the working checklist — for the phased overview see
[ROADMAP.md](ROADMAP.md). Keep this file short: only what's in flight or next up.

## Repo bootstrap (not blocking, pick up anytime)

- [x] Initialize repo, README, ROADMAP, LICENSE
- [ ] Add `.github/ISSUE_TEMPLATE` (bug report, feature request)
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Set up CI: lint + typecheck on push (GitHub Actions)
- [ ] Add branch protection on `main` once CI exists

## Phase 1 & 2 — done

Core platform (auth, projects, entities/fields, generation engine) and
simulation (relationships, rules, formulas, stateful entities/workflows) are
both live, backend and frontend, verified end-to-end in a browser. Full
checklists: ROADMAP.md Phases 1–2. Known simplifications carried forward —
`many_to_many` generates like `one_to_many`, rules/formulas are same-row only
(no cross-entity), event-style triggers aren't implemented, workflows are a
bounded per-call random walk with no cross-call record identity yet.

## Phase 3 — done (file outputs, database connectors, REST output, plugin
manager, WebSocket streaming)

Full checklist: ROADMAP.md Phase 3. Highlights:

- Excel + project-level CSV zip; `DatabaseConnection` (PostgreSQL v1, MySQL
  modeled but rejected until that driver lands), writing through SQLAlchemy
  Core with parameterized inserts — never string-formatted SQL.
- `RestOutput` and `WebSocketStream`: both public, unauthenticated,
  token-gated (same trust model as a webhook URL) — pull vs. push versions
  of the same idea. The plugin manager is a read-only aggregate
  (`GET /projects/{id}/outputs`) over these typed tables, not a new
  polymorphic model.
- WebSocket streaming is connection-scoped: the production loop *is* the
  WebSocket handler's loop, no persisted "running" state. Kafka/MQTT (not
  started) won't have a client connection to hang that off of and will need
  a real background-task execution model instead.
- Two real bugs found and fixed *while verifying*, not by inspection: Base
  UI's `Select.Value` showing raw ids instead of labels, and a websocket
  route that bypassed the test suite's DB session override by importing
  `SessionLocal` directly instead of looking it up on the module each call.

## Phase 4, parts 1–5: probability, trend, correlation, error injection,
lookup tables — done

Full detail for each lives in ROADMAP.md Phase 4; condensed here:

- **Probability**: `EntityField.enum_weights` for `random.choices`-based
  weighted selection.
- **Trend**: `Trend` attaches to one numeric field; value is a function of
  the row's 0-indexed position within the *current batch* (position resets
  every `generate` call — documented, not a silent gap).
- **Correlation** (same-entity): ~90% already built via formula fields
  referencing earlier fields on their own row; closed the real gap
  (formulas being fully deterministic) with `noise(stddev)`/`uniform(low,
  high)` in the shared expression evaluator. Cross-entity correlation
  merged into the cross-entity-rules backlog item below.
- **Error injection**: `ErrorInjection` attaches to one field (rate 0–1 +
  a set of `error_types`), corrupting its value in `_corrupt_value` after
  it's otherwise fully computed. Documented interaction: a rule on the same
  field evaluates post-corruption, so it can discard every corrupted row.
- **Lookup tables**: `LookupTable` (project-scoped, uploaded once as
  CSV/Excel/JSON) + `LookupAttachment` (per-field, draws from one column).
  Resolved design question: reuses the exact same `fk_pools` mechanism a
  `Relationship`'s foreign key already uses, rather than a new "sample from
  a table" path — and because a lookup doesn't need another entity
  generated first, it works from single-entity generation too, not just
  project-wide (a real capability advantage over relationships).
- 55 new tests across all five, 111 passed / 3 skipped total, lint clean.
  Verified end-to-end in a browser for each (weighted enum distribution
  matched configured weights; linear trend gave an exact arithmetic
  sequence; temperature/humidity correlation came back with Pearson
  r = -0.985; a rate-1 null injection returned 10/10 nulls; a lookup
  attachment returned 10/10 rows drawing the uploaded value).

## Now — Phase 4, remainder

Not started. Remaining items: event triggers (threshold-based actions,
e.g. `temp > 80 → fire alert` — needs a design pass on what "firing" means
without a notification system yet; likely starts as a flagged/annotated
row rather than an actual external send), timeline replay, geographic
simulation, user-behavior simulation, API-behavior simulation, and
log/security-event generators. Log/security-event generators are mostly
"more Faker-shaped generation content" (closer to Phase 1 field types than
a new engine) — likely simpler than they sound once there's a reason to
build them.

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules + correlation (Phase 2/4, stretch — a formula or
      rule seeing another entity's already-generated data, not just its own
      row; both features hit this same wall independently, see above)
- [ ] Kafka/MQTT streaming outputs (Phase 3, needs the background-task
      execution model noted above)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5). Phase 3 outputs are exactly the kind of thing that
  needs to be added/removed per-deployment later.
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- `app/services/expressions.py` is shared infrastructure — reuse it for anything
  else that needs a user-authored expression (event triggers, cross-entity
  rules/correlation) rather than writing a second evaluator. Before building a new
  "engine" as its own model/table, check whether it's actually just a formula or
  rule with a missing capability (like `noise()`/`uniform()` turned out to be for
  correlation) — cheaper to extend the evaluator than to add a new concept.
- When verifying Select/dropdown UI by browser automation, screenshot the
  *closed* control after selecting, not just the open dropdown or the
  eventual result — that's the gap that let the UUID-label bug ship.
- When a route bypasses normal `Depends(...)` dependency injection (the
  websocket stream loop has to, for a fresh short-lived session per tick),
  it also bypasses the test suite's override mechanism unless it looks the
  factory up dynamically (`module.attr`, not `from module import attr`).
  Check this specifically for any future code that touches the DB outside a
  request-scoped dependency.
