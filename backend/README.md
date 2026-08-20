# SynthFlow backend

FastAPI service: auth, projects, entities/fields, and the batch generation engine.

## Local dev (Docker, recommended)

```bash
docker compose up -d --build      # from the repo root
docker compose exec backend alembic upgrade head
```

API is at `http://localhost:8001` (mapped from the container's 8000 — see
`docker-compose.yml` if you need to change the host ports; 5432/8000 were left
free for other local services). Postgres is at `localhost:5433`.

## Local dev (no Docker)

Requires Python 3.11+. This repo uses [uv](https://github.com/astral-sh/uv) for
dependency management:

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]" --python .venv/bin/python
cp .env.example .env   # edit DATABASE_URL if not using the default sqlite file
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

## Tests & lint

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Layout

```
app/
  core/      settings, JWT/password helpers
  db/        SQLAlchemy engine/session/base
  models/    User, Project, Entity, EntityField
  schemas/   Pydantic request/response models
  api/       routes + auth dependency
  services/  generation engine (Phase 2+ rule/formula/workflow engines land here)
alembic/     migrations
tests/       pytest, in-memory sqlite per test
```
