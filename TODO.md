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
- WebSocket streaming is connection-scoped by design: the production loop
  *is* the WebSocket handler's loop, so there's no persisted "running" state
  to leak across a restart. This only works because a client connection
  gives the loop something to hang off of — Kafka/MQTT (not started) won't
  have that and will need a real background-task execution model instead.
- Two real bugs found and fixed *while verifying*, not by inspection: Base
  UI's `Select.Value` showing raw ids instead of labels (across every
  affected picker, not just the one being tested), and a websocket route
  that bypassed the test suite's DB session override by importing
  `SessionLocal` directly instead of looking it up on the module each call.

## Phase 4, parts 1–2: probability + trend engines — done

- `EntityField.enum_weights`: optional array parallel to `enum_values` for
  weighted-random selection (`random.choices`); `None` keeps prior uniform
  behavior. Validated server-side at create/update time.
- `Trend`: attaches to one numeric field; its value is a function of the
  row's 0-indexed position within the *current batch* — linear, exponential,
  logistic, seasonal, cyclic, random_walk, each with type-specific `params`
  plus optional `noise`. Resolved design question: **position resets to 0
  every `generate` call** rather than persisting across a WebSocket stream's
  ticks — a stream replays the trend across each push's batch_size rows
  instead of continuing smoothly tick to tick. That's a real, documented
  limitation (in `Trend`'s docstring), not a silent gap — genuine cross-tick
  continuity would need trend state persisted on the stream itself, not
  built yet. `increasing`/`decreasing` from the spec are `linear` with the
  slope's sign, not separate types.
- Neither feature needed changes anywhere else in the pipeline — formulas,
  rules, relationships, and workflows all just consume whatever value a
  field ends up with, regardless of how it was produced. 18 new tests
  across both, 79 passed / 3 skipped total, lint clean.
- Verified end-to-end in a browser against the full docker-compose stack for
  both: a weighted enum's real distribution matched its configured weights
  closely (65/10/5/20 configured → 64/11/5.3/20 observed over 300 rows); a
  linear trend (start=20, slope=0.5) produced an exact 20, 20.5, 21, ...,
  24.5 sequence over 10 rows, not just "some variation."

## Now — Phase 4, part 3: correlation engine

Not started. Needs the same "what does a row's position mean" foundation
that trends just established — correlating two fields/entities (e.g.
temperature ↑ → humidity ↓) implies they share some ordering or common
per-row position, which trends now provide (batch position) but nothing
before did. Reasonable approach: let a correlated field be defined as a
function of *another field's already-generated value on the same row*
(e.g. `humidity = 100 - temperature * factor`) rather than inventing new
cross-field machinery — check whether this is actually already expressible
with the existing formula engine (`app/services/expressions.py`) before
building a separate "correlation" concept. If a formula can already say
`humidity = 100 - temperature * 0.8`, the "correlation engine" may just be
UI/framing on top of formulas for two numeric fields, not new backend code.

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules (Phase 2, stretch)
- [ ] Kafka/MQTT streaming outputs (Phase 3, needs the background-task
      execution model noted above)
- [ ] Error injection, timeline replay, lookup tables, geographic/user-
      behavior/API-behavior simulation, log + security-event generators
      (Phase 4, remainder — log/security-event generators are mostly "more
      Faker-shaped generation content," likely simpler than they sound now
      that trend/probability exist to build on)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5). Phase 3 outputs are exactly the kind of thing that
  needs to be added/removed per-deployment later.
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- `app/services/expressions.py` is shared infrastructure — reuse it for anything
  else that needs a user-authored expression (event triggers, cross-entity rules,
  possibly correlation — see Phase 4 part 3 above) rather than writing a second
  evaluator.
- When verifying Select/dropdown UI by browser automation, screenshot the
  *closed* control after selecting, not just the open dropdown or the
  eventual result — that's the gap that let the UUID-label bug ship.
- When a route bypasses normal `Depends(...)` dependency injection (the
  websocket stream loop has to, for a fresh short-lived session per tick),
  it also bypasses the test suite's override mechanism unless it looks the
  factory up dynamically (`module.attr`, not `from module import attr`).
  Check this specifically for any future code that touches the DB outside a
  request-scoped dependency.
