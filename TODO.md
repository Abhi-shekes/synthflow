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

## Phase 3, parts 1–2: file outputs + database connectors — done

- Excel (single-entity and multi-sheet project-level) and a project-level CSV
  zip, alongside the CSV/JSON that already existed. Excel keeps extra
  generation-time columns (e.g. `<field>_history`) that CSV drops — a
  deliberate difference, not an inconsistency to fix.
- `DatabaseConnection` (PostgreSQL only for v1; MySQL modeled but rejected
  until that driver is added): test-connection and push actions, writing
  through SQLAlchemy Core with parameterized inserts and a strict identifier
  check — never string-formatted SQL.
- Verified for real: pushed rows through the actual UI into a *separate*
  throwaway Postgres container on the same docker network, then confirmed
  with `psql` directly that the table and data landed there.
- Found and fixed a real bug while doing that verification, not specific to
  this feature: Base UI's `Select.Value` shows the raw id instead of the
  label when given no `items` map. Fixed across every affected `<Select>`
  (relationship/workflow pickers too) via a function-`children` label lookup.
  Caught only because verification screenshotted a *closed* dropdown for the
  first time — worth remembering when writing future browser checks.

## Phase 3, part 3: REST output + plugin manager — done

- `RestOutput`: `GET /public/rest/{token}` — no auth, unguessable token is
  the access control (same trust model as a webhook URL), fresh batch every
  call, respects the entity's rules/workflows.
- Plugin manager resolved as a read-only aggregate (`GET
  /projects/{id}/outputs`) over the existing typed output tables
  (`DatabaseConnection`, `RestOutput`), not a new polymorphic model — kept
  consistent with how Relationship/Rule/Workflow are already separate typed
  tables rather than one generic table. An output is "enabled" by creating a
  row in its own table, "disabled" by deleting it.
- Verified for real: created an endpoint through the UI, fetched it with a
  plain unauthenticated request (no headers) and got real generated rows
  back, then confirmed deleting it 404s the same URL.

## Now — Phase 3, part 4: streaming outputs (Kafka, MQTT, WebSocket)

Not started. This is the one Phase 3 item that doesn't fit the current
request/response shape — resolve the design question below before writing
models or routes, the same way stateful entities and the plugin-manager
shape got a design pass first rather than being squeezed in.

**The open question:** every output built so far is pull-based — something
asks, `generate` runs synchronously, a response comes back. Streaming is
push-based: SynthFlow has to *keep producing* onto a topic/queue/socket
without being asked again, which means a long-running background task the
request/response cycle can't hold open. That needs an actual async execution
model (Celery+Redis are already in the stated tech stack for this reason —
see README.md) — start/stop lifecycle for a stream, and somewhere to persist
"this project has an active Kafka producer running." Don't bolt a
`while True: produce()` onto a FastAPI request handler.

- [ ] Decide the execution model (Celery worker? asyncio background task
      inside the API process? a separate process per active stream?) before
      touching models/routes
- [ ] A `Stream` (or similar) model: target (kafka/mqtt/websocket) + broker
      config + entity + rate (events/sec) + status (running/stopped)
- [ ] Start/stop lifecycle, not just create/delete — a streaming output has
      runtime state a REST/DB output doesn't
- [ ] WebSocket is probably the cheapest to prove the execution model on
      first (no external broker needed to test it) — build that one first,
      then Kafka/MQTT once the lifecycle plumbing is proven out

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Cross-entity rules (Phase 2, stretch)
- [ ] Trend/correlation/probability engines (Phase 4)
- [ ] Error injection + timeline replay (Phase 4)

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
