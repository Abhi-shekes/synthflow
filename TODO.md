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

- [x] Relationship model (`relationships` table: type + source/target entity+field)
- [x] Relationship CRUD API — `backend/app/api/routes/relationships.py`
- [x] Project-level `POST /projects/{id}/generate` — generates every entity in
      dependency order (topological sort over relationships) and draws a
      source entity's foreign-key values from its target's already-generated
      rows (`generate_project` in `backend/app/services/generator.py`)
- [x] Relationship builder UI (plain cascading-select form, not drag-and-drop) +
      "Generate all entities" view on the project page
- Verified end-to-end in a real browser: created a one-to-many Customer→Order
  relationship, generated both, confirmed every `Order.customer_ref` value is
  one of the actually-generated `Customer.customer_id` values.
- Known simplification: `many_to_many` is accepted as a type but currently
  generated the same as `one_to_many` (no join-table modeling yet).

## Now — Phase 2, part 2: rules, formulas, stateful entities

- [ ] Rules engine: field-level and cross-entity conditions (e.g. `price > 0`,
      `if payment_status == "success" then ...`) — needs a small expression
      model + evaluator, not a raw `eval`
- [ ] Formula engine: derived fields computed from other fields on the same row
      (e.g. `total = price * quantity`), evaluated after the row's own fields
      are generated
- [ ] Stateful entities: a field (or the entity) declares allowed states +
      transitions (e.g. `created → packed → shipped → delivered`); generation
      picks a valid state instead of pure randomness
- [ ] Workflow / state machine builder UI — can start as a simple state-list +
      transition-list form like the relationship builder; the React Flow visual
      canvas from the spec is a later polish pass

## Backlog (not started, roughly in order)

- [ ] Generated-field and auto-increment field support (Phase 2)
- [ ] Output plugin manager + REST/Kafka/MQTT outputs (Phase 3)
- [ ] Trend/correlation/probability engines (Phase 4)
- [ ] Error injection + timeline replay (Phase 4)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5).
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- Generation order now matters: `generate_project` topologically sorts entities
  by relationship dependency before generating. Rules/formulas that reference
  *other entities'* fields (cross-entity rules) will need to hook into that same
  ordering rather than introducing a second, separate dependency pass.
- The rules/formula engine should NOT be a raw `eval()` over user input — pick a
  small safe-expression approach (e.g. a restricted AST evaluator or a tiny
  parser for a limited grammar) before wiring it to the API.
