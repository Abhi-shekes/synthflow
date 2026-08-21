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
- Every output verified against real infrastructure, not just the app's own
  tests: pushed rows into a separate throwaway Postgres container and
  confirmed with `psql`; fetched REST/WebSocket outputs with plain
  unauthenticated requests from outside the app entirely.
- Two real bugs found and fixed *while verifying*, not by inspection: Base
  UI's `Select.Value` showing raw ids instead of labels (across every
  affected picker, not just the one being tested), and a websocket route
  that bypassed the test suite's DB session override by importing
  `SessionLocal` directly instead of looking it up on the module each call.
  Both were only caught because verification exercised the real UI/DB path
  end-to-end instead of stopping at "the code looks right."

## Now — Phase 4: advanced simulation

Not started. Bigger and more varied than Phase 3 — trend/correlation/
probability engines, error injection, timeline replay, lookup tables,
geographic simulation, user-behavior simulation, API-behavior simulation, log
generators, security event generator (see ROADMAP.md Phase 4 for the full
list). Don't default to doing these in list order; some have real design
questions worth a pass first, the way stateful entities and streaming did:

- **Trend engine** has the same "what does time mean here" question stateful
  entities had. A `generate` call produces an unordered batch of N rows —
  does a linear/seasonal/cyclic trend apply *across that batch* (row N's
  value is a function of its position in the batch) or *across ticks of a
  live stream* (this connects naturally to the WebSocket work just done —
  each push is the next point on the trend)? Those are different features
  wearing the same name. Resolve which one (or both, as separate concepts)
  before modeling it.
- **Probability engine** (weighted categorical generation) is the smallest,
  most self-contained item here — it's an upgrade to the existing `enum`
  field type (add optional weights) rather than a new subsystem. Reasonable
  first pick if you want something scoped like the last several rounds
  rather than opening the trend-engine design question immediately.
- **Correlation engine** needs the trend engine's "what does a row's position
  mean" question answered too (correlating two fields/entities implies some
  shared ordering or shared random state between them).
- Log/security-event generators are mostly "more Faker-shaped generation
  content," closer in spirit to Phase 1's field types than to a new engine —
  likely simpler than they sound once trend/probability exist to build on.

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules (Phase 2, stretch)
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
  else that needs a user-authored expression (event triggers, cross-entity rules)
  rather than writing a second evaluator.
- When verifying Select/dropdown UI by browser automation, screenshot the
  *closed* control after selecting, not just the open dropdown or the
  eventual result — that's the gap that let the UUID-label bug ship.
- When a route bypasses normal `Depends(...)` dependency injection (the
  websocket stream loop has to, for a fresh short-lived session per tick),
  it also bypasses the test suite's override mechanism unless it looks the
  factory up dynamically (`module.attr`, not `from module import attr`).
  Check this specifically for any future code that touches the DB outside a
  request-scoped dependency.
