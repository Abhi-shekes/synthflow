# TODO

Active task list. This is the working checklist — for the phased overview see
[ROADMAP.md](ROADMAP.md). Keep this file short: only what's in flight or next up.

## Now — repo bootstrap

- [x] Initialize repo, README, ROADMAP, LICENSE
- [ ] Add `.github/ISSUE_TEMPLATE` (bug report, feature request)
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Set up CI: lint + typecheck on push (GitHub Actions)
- [ ] Add branch protection on `main` once CI exists

## Next — backend skeleton

- [ ] `backend/` FastAPI app: `app/main.py`, settings via Pydantic `BaseSettings`
- [ ] `/healthz` route
- [ ] SQLAlchemy models: `User`, `Project`
- [ ] Alembic migrations wired up, initial migration committed
- [ ] JWT auth: signup, login, refresh, current-user dependency
- [ ] `docker-compose.yml`: backend + Postgres for local dev
- [ ] Basic pytest setup with one passing test per route

## Next — frontend skeleton

- [ ] `frontend/` Next.js app (App Router, TypeScript, Tailwind, shadcn/ui)
- [ ] Auth pages: login, signup
- [ ] Project list page + create-project flow
- [ ] TanStack Query + Zustand wiring for API calls and client state
- [ ] Point frontend at backend via env-configured API base URL

## Then — first vertical slice (entity → generate → view)

- [ ] Entity model: fields with type + constraints (string, int, float, bool,
      date, datetime, uuid, enum, array, object, json)
- [ ] Entity CRUD API + schema builder UI (no relationships yet — Phase 2)
- [ ] Generation engine: batch-generate N rows for one entity using
      Faker/Mimesis/Polyfactory, respecting field constraints
- [ ] "Generate" button in UI → table/JSON preview of generated rows
- [ ] Export generated batch as JSON/CSV (minimum viable output, ahead of the
      full Phase 3 plugin system)

## Backlog (not started, roughly in order)

- [ ] Relationship builder (Phase 2)
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
