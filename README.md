# SynthFlow

**Open-source synthetic data simulation platform.**
Design realistic data. Simulate real-world behavior. Deliver it anywhere.

---

## Why SynthFlow

Most "fake data" tools generate isolated, static records. Real systems need data
that *behaves* — entities with state, relationships that hold together, rules that
fire under conditions, and streams that look and feel like production traffic.

Teams end up hand-rolling one-off scripts to fill that gap, and those scripts rot.

SynthFlow is a configurable simulation platform for modeling entire systems —
schemas, relationships, business rules, workflows, and time-based behavior — and
publishing the result through APIs, databases, message brokers, or files.

AI is completely optional. SynthFlow works fully offline with zero LLM calls; if you
want it, you bring your own key (OpenAI, Claude, Gemini, Mistral, Groq, OpenRouter,
Ollama, LM Studio, or any OpenAI-compatible endpoint).

## What it does

- **Visual schema builder** — entities, field types, constraints, formulas, foreign keys
- **Relationship builder** — one-to-one, one-to-many, many-to-many, parent-child
- **Stateful entities** — records that move through defined state transitions, not
  random rows (e.g. `Created → Packed → Shipped → Delivered`)
- **Workflow / state machine builder** — visual state machines for IoT, manufacturing,
  logistics, robotics
- **Rules engine** — logical, mathematical, conditional, and cross-entity rules
- **Formula engine** — derived fields computed automatically (`Total = Price × Quantity`)
- **Simulation engine** — batch generation, live streaming, time acceleration,
  peak-hour/holiday schedules, infinite streams
- **Trend, correlation, and probability engines** — seasonal/cyclic/random-walk trends,
  correlated signals (temperature ↑ → humidity ↓), weighted distributions
- **Event triggers & error injection** — threshold-based events, missing values,
  corrupted payloads, out-of-order and delayed events, timeouts
- **Timeline replay** — replay historical datasets as live streams at any speed
- **Domain simulators** — geographic/GPS, user behavior, API responses, logs
  (Kubernetes/Docker/Nginx), and security events
- **Digital twin modeling** — compose interacting subsystems (e.g. a factory: machines,
  sensors, workers, maintenance, alarms) into one simulation
- **Templates** — ready-made projects for banking, stock market, smart city, weather,
  hospital, manufacturing, CCTV, logistics, GPS fleet, retail, IoT
- **Live monitoring** — events/sec, active streams, resource usage, error rates

## Architecture

```
Next.js UI
   │
FastAPI Backend
   │
   ├── Schema Engine
   ├── Rules Engine
   ├── Workflow Engine
   │
   Simulation Engine
   │
   Plugin Manager
   │
   ├── REST        ├── Kafka       ├── MQTT
   ├── WebSocket    ├── PostgreSQL  ├── CSV/JSON
```

Everything past the core is a plugin. Install only what you need — a REST-only
deployment doesn't pull in Kafka, MongoDB, or MQTT dependencies. See
[ROADMAP.md](ROADMAP.md) for the full plugin catalogue.

## Tech stack

| Layer | Choices |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, React Flow, TanStack Query, Zustand, React Hook Form, Monaco Editor, Recharts |
| Backend | FastAPI, SQLAlchemy, Pydantic, Uvicorn |
| Database | PostgreSQL, SQLite |
| Synthetic data | Faker, Mimesis, Polyfactory |
| Streaming | Kafka, MQTT, RabbitMQ, WebSockets |
| Background jobs | Postgres-backed queue (`SELECT … FOR UPDATE SKIP LOCKED`) |
| Monitoring | Prometheus, Grafana, Loki |
| Auth | JWT |
| Containers | Docker, Docker Compose |

## Project status

**Phases 1–8 are live**, backend and frontend, each verified end to end
rather than only by test suite:

- **1–2** core platform, relationships, rules, formulas, stateful workflows
- **3** outputs: CSV/JSON/Excel, PostgreSQL push, REST, WebSocket, Kafka, MQTT
- **4** advanced simulation: trends, probability, error injection, lookup
  tables, event triggers, timeline replay, geo routes, log/security presets
- **5** extensibility: generator/rule-function/output plugins, project
  export–import, 11 starter templates, a monitoring dashboard, modular install
- **7** schema import — build a project from a live database, SQL dump,
  JSON Schema/OpenAPI, or a sample file
- **8** scale: streaming generation with no memory ceiling, a Postgres-backed
  job queue with progress and cancellation, cron schedules, and background
  producers that survive a restart
- **9** learn from real data: upload sample files and get fitted distributions,
  observed category frequencies, correlations between columns and relationships
  between files — as an ordinary editable project, using statistics rather than
  a language model
- **10** privacy: personal data detected and replaced with synthetic
  generators during profiling (so no value from your file reaches the
  project), k-anonymity and l-diversity measured on generated output, and
  connection passwords encrypted at rest

Phase 6 (the optional AI layer) is deliberately unstarted — nothing depends
on it. Phases 11–16 are planned. See [ROADMAP.md](ROADMAP.md) for the phased
plan, including the tradeoffs and known limits recorded per item, and
[TODO.md](TODO.md) for the active task list.

## Getting started

```bash
git clone https://github.com/Abhi-shekes/synthflow.git
cd synthflow
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8001](http://localhost:8001) (interactive docs at `/docs`)

### Optional services

Extras are behind Compose profiles, so the default `docker compose up`
stays a three-container stack. Either pick them with the wizard:

```bash
synthflow init                              # interactive
synthflow init --services kafka,monitoring --yes   # or not
docker compose build backend && docker compose up -d
```

`synthflow init` writes a single `.env` with `COMPOSE_PROFILES` (which
services start) and `SYNTHFLOW_EXTRAS` (which optional Python
dependencies go into the backend image). That second one is what makes
the install genuinely modular — a Kafka-only install never pulls
`aiomqtt` at all, and the UI greys out the MQTT output and tells you how
to enable it.

Or turn profiles on directly, without the wizard:

```bash
docker compose --profile monitoring up -d   # Prometheus + Grafana + Loki
docker compose --profile kafka up -d        # Redpanda, for Kafka outputs
docker compose --profile mqtt up -d         # Mosquitto, for MQTT outputs
```

With the `monitoring` profile up, Grafana is at
[http://localhost:3001](http://localhost:3001) — no login, already
provisioned with a **SynthFlow overview** dashboard showing rows/sec by
source, active producers and connected clients, backend CPU/memory,
generation latency, and errors. The backend exposes raw metrics at
`/metrics` and container logs land in Loki.

See `backend/README.md` and `frontend/README.md` for running each service
without Docker.

## Contributing

This project is just getting started and is open to contributors. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
