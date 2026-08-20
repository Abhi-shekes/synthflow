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
download) are both live and wired together via `docker-compose.yml`
(postgres:5433, backend:8001, frontend:3000). Verified end-to-end — including
the CSV download — with a headless-browser smoke test against the full
containerized stack. Full checklist: ROADMAP.md Phase 1.

## Now — Phase 2: relationships (backend first)

- [ ] Relationship model: one-to-one, one-to-many, many-to-many, parent-child —
      a source entity/field pointing at a target entity/field, plus cardinality
- [ ] Relationship CRUD API (likely nested under `/projects/{id}/entities` or its
      own `/projects/{id}/relationships`)
- [ ] Generation engine: when generating a dependent entity, pull real
      foreign-key values from an already-generated (or existing) parent batch
      instead of random ones — this is the main behavioral change from Phase 1
- [ ] Relationship builder UI — start with a plain form (source entity/field →
      target entity/field + cardinality); the drag-and-drop React Flow canvas
      from the spec is a later polish pass, not a blocker for Phase 2 to land

## Backlog (not started, roughly in order)

- [ ] Rules + formula engine (Phase 2)
- [ ] Stateful entities + workflow builder (Phase 2)
- [ ] Output plugin manager + REST/Kafka/MQTT outputs (Phase 3)
- [ ] Trend/correlation/probability engines (Phase 4)
- [ ] Error injection + timeline replay (Phase 4)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5).
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- Relationships change generation order: a dependent entity can't be generated
  before its parent has rows to reference. The generation engine will need an
  explicit dependency/topological ordering once relationships land — don't bolt
  this on after the fact.
