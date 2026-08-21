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

## Phase 4, parts 1–3: probability, trend, correlation engines — done

- **Probability**: `EntityField.enum_weights`, optional array parallel to
  `enum_values`, for `random.choices`-based weighted selection.
- **Trend**: `Trend` attaches to one numeric field; its value is a function
  of the row's 0-indexed position within the *current batch* — linear,
  exponential, logistic, seasonal, cyclic, random_walk. Resolved design
  question: position resets to 0 every `generate` call rather than
  persisting across a WebSocket stream's ticks (documented limitation, not
  a silent gap — see `Trend`'s docstring).
- **Correlation** (same-entity): turned out to be ~90% already built —
  formula fields can already reference any earlier field on their own row.
  The real gap was formulas being fully deterministic; closed by adding
  `noise(stddev)` and `uniform(low, high)` to the shared expression
  evaluator, so `humidity = 100 - temperature * 1.5 + noise(3)` gives a
  real, scattered correlation instead of new backend machinery.
  Cross-entity correlation ("Stock A ↑ → Stock B ↑" across two entities)
  merged into the cross-entity-rules backlog item below — same underlying
  need (seeing another entity's data, not just this row).
- None of the three needed changes to relationships/rules/workflows — they
  all just consume whatever value a field ends up with. 28 new tests across
  all three, 84 passed / 3 skipped total, lint clean.
- Verified end-to-end in a browser for all three: a weighted enum's real
  distribution matched its configured weights (65/10/5/20 → 64/11/5.3/20
  over 300 rows); a linear trend produced an exact arithmetic sequence over
  10 rows; a temperature/humidity correlation came back with a real Pearson
  r of -0.985 across 100 rows with 100 distinct humidity values (genuine
  scatter, not a dead-flat line).

## Phase 4, part 4: error injection — done

- `ErrorInjection` attaches to one field (same per-field pattern as
  Rule/Workflow/Trend): a `rate` (0–1) and a set of `error_types` (`null`,
  `empty`, `duplicate`, `truncate`, `wrong_type`, `out_of_range`), validated
  against the field's type at creation time.
- Corruption happens in `_corrupt_value`, applied *after* a field's value is
  otherwise fully computed (formula, trend, workflow, or plain random) — it
  doesn't care how the clean value was produced. `duplicate` needed
  `previous_row` threaded through `generate_rows`'s per-position loop (the
  first row has no previous row, so it keeps its own value; every later row
  copies forward whatever the row before it ended up with, corrupted or not).
- Documented, deliberately unresolved interaction: a rule evaluates the row
  *after* corruption, so a rule constraining the same field can discard every
  corrupted row until the retry budget is spent — reusing the existing
  discard-and-retry mechanism as-is rather than special-casing it.
- 12 new backend tests (one per error type's effect, validation rejections,
  one-per-field constraint, delete, the rule-interaction failure mode), 96
  passed / 3 skipped total, lint clean. Verified end-to-end in a browser:
  configured a `null` injection at rate 1 on a string field through the real
  UI, generated 10 rows, all 10 came back `null`, zero console errors.

## Now — Phase 4, remainder

Not started. Remaining items, roughly in a reasonable build order:

- **Lookup tables** (upload CSV/Excel/JSON as reference data, generate by
  sampling from it) is the next natural pick — needs file upload handling
  and storage, which nothing built so far has needed.
- Timeline replay, geographic simulation, user-behavior simulation,
  API-behavior simulation, and log/security-event generators remain
  unscoped. Log/security-event generators are mostly "more Faker-shaped
  generation content" (closer to Phase 1 field types than a new engine) —
  likely simpler than they sound once there's a reason to build them.

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
