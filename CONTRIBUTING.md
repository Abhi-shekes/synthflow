# Contributing to SynthFlow

Read [ROADMAP.md](ROADMAP.md) for the phased plan and the reasoning behind
each decision, [TODO.md](TODO.md) for what is in flight, and
[README.md](README.md) for what the software does. Those three are kept
honest: unchecked boxes carry the reason they are unchecked, and several
items are deliberately unbuilt and say so.

## The development loop

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

Backend on `:8001`, frontend on `:3000`.

**Both services hot-reload. You almost never need to rebuild.** The source
is bind-mounted into each container, the backend runs `uvicorn --reload` and
the frontend runs `next dev`, so a saved file is live in about a second.

| You changed | What to do |
|---|---|
| Any `.py` under `backend/` | Nothing — uvicorn reloads in place |
| Any `.ts`/`.tsx` under `frontend/` | Nothing — Next.js Fast Refresh |
| `backend/pyproject.toml` (a dependency) | `docker compose build backend && docker compose up -d backend` |
| `frontend/package.json` (a dependency) | `docker compose build frontend && docker compose up -d frontend` |
| `SYNTHFLOW_EXTRAS` in `.env` | Rebuild the backend — extras are installed at build time |
| A new Alembic migration | `docker compose exec backend alembic upgrade head` |
| `docker-compose.yml`, or a service's env | `docker compose up -d <service>` |
| A mounted config (`dex/`, `mosquitto/`, `monitoring/`) | `docker compose restart <service>` — mounted read-only, so the file is already current |

If saving a file does *not* trigger a reload, your filesystem is not
propagating inotify events — this happens on Docker Desktop's osxfs and
gRPC-FUSE, on NFS, and on some Windows setups. Set `WATCHPACK_POLLING=true`
in `.env` and restart the frontend. It is off by default because polling
wakes the CPU on every interval whether anything changed or not.

Both services have a `.dockerignore`. Without them the build context was
1.3 GB — `backend/.venv` at 400 MB and `frontend/node_modules` plus `.next`
at nearly a gigabyte — all of which is rebuilt inside the image anyway. With
them it is about 3 MB, which is the difference between a three-second
rebuild and a slow one.

`node_modules` and `.next` are also masked by anonymous volumes, so the
container keeps its own: the host's `node_modules` may hold binaries built
for a different platform, and `.next` must not be shared with a host-side
`next build`.

## Running the checks

```bash
# backend, from backend/
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .

# frontend, from frontend/
npx tsc --noEmit && npm run lint
```

CI runs the backend suite twice — once with no optional extras and once with
all of them. **Every optional client is imported inside the function that
uses it**, never at module scope, or the core leg breaks. Keep it that way.

## Optional services

Anything a connector talks to is behind a compose profile, so a default
`up` starts only what SynthFlow itself needs:

```bash
docker compose --profile mysql --profile mongo up -d    # push targets
docker compose --profile s3 up -d                       # MinIO
docker compose --profile kafka --profile mqtt up -d     # brokers
docker compose --profile rabbitmq up -d
docker compose --profile monitoring up -d               # Prometheus, Grafana, Loki
docker compose --profile sso up -d                      # Dex, a real OIDC provider
```

Their host ports are deliberately non-default (MySQL `3307`, MongoDB
`27117`, MinIO `9100/9101`, RabbitMQ `5673/15673`) so trying SynthFlow does
not collide with a database you already run locally.

## What a good change looks like

- **One change per PR.** Reference the ROADMAP or TODO item it addresses.
- **Tests that name the behaviour**, not the implementation. The suite reads
  as sentences — `test_a_viewer_may_read_but_not_write`, not `test_access_1`.
- **Derive test expectations from the registry under test.** Hardcoded sets
  and counts have broken four times here for reasons that said nothing about
  the behaviour.
- **Say why in a comment when the why is not obvious**, especially when you
  chose the less obvious option. Most of this codebase's comments explain a
  decision rather than restate the code.
- **Verify against real infrastructure, not mocks.** Nearly every genuine bug
  in this project was found that way and would have passed the unit suite: a
  DECIMAL column profiling as a string, ORC writing an unopenable zero-row
  file, RabbitMQ silently discarding messages, half of all API keys failing
  to parse. The compose profiles above exist for exactly this.
- **If it has a UI, open it in a browser.** Several defects here typechecked,
  passed tests, and were obvious on sight.
- **Be honest in ROADMAP/TODO.** An unchecked box with a reason is worth more
  than a checked one that overstates.

## Plugin contributions

Generator, rule-function and output plugins are documented in Phase 5 of the
roadmap and shipped in `examples/example-plugin/`. Plugins are a
high-value way to contribute without touching core.

## Code of conduct

Be respectful and constructive. Disagreements about design are fine and
expected; personal attacks are not.
