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

- [x] `backend/` FastAPI app: `app/main.py`, settings via Pydantic `BaseSettings`
- [x] `/healthz` route
- [x] SQLAlchemy models: `User`, `Project` (`Entity`/`EntityField` added early —
      needed together for the vertical slice below)
- [x] Alembic migrations wired up, initial migration committed
- [x] JWT auth: signup, login, refresh, current-user dependency
- [x] `docker-compose.yml`: backend + Postgres for local dev (host ports 5433/8001
      to avoid clashing with other local services — see docker-compose.yml)
- [x] Basic pytest setup with one passing test per route (8 tests, `backend/tests/`)

## Next — frontend skeleton

- [x] `frontend/` Next.js app (App Router, TypeScript, Tailwind, shadcn/ui)
- [x] Auth pages: login, signup
- [x] Project list page + create-project flow
- [x] TanStack Query + Zustand wiring for API calls and client state
- [x] Point frontend at backend via env-configured API base URL (`NEXT_PUBLIC_API_URL`)

## Then — first vertical slice (entity → generate → view)

- [x] Entity model: fields with type + constraints (string, int, float, bool,
      date, datetime, uuid, enum, array, object, json)
- [x] Entity CRUD API (no relationships yet — Phase 2) — `backend/app/api/routes/entities.py`
- [x] Schema builder UI v1 — add/delete entities and fields via forms/dialogs
      (no drag-and-drop yet, that's the Phase 2+ React Flow work)
- [x] Generation engine: batch-generate N rows for one entity using Faker,
      respecting type/min/max/regex/enum/unique/nullable constraints —
      `backend/app/services/generator.py`
- [x] "Generate" button in UI → table preview of generated rows
- [ ] Export generated batch as CSV (JSON is already the API's native response and
      the UI preview; CSV endpoint still open, ahead of the full Phase 3 plugin system)

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
