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
| Background jobs | Celery, Redis |
| Monitoring | Prometheus, Grafana, Loki |
| Auth | JWT |
| Containers | Docker, Docker Compose |

## Project status

Phase 1 (core platform) is live: auth, projects, entities/fields with
constraints, and batch generation (JSON + CSV), backend and frontend both
working end-to-end. Phase 2 (relationships, rules, stateful entities) is next.
See [ROADMAP.md](ROADMAP.md) for the phased plan and [TODO.md](TODO.md) for
the active task list.

## Getting started

```bash
git clone https://github.com/Abhi-shekes/synthflow.git
cd synthflow
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8001](http://localhost:8001) (interactive docs at `/docs`)

See `backend/README.md` and `frontend/README.md` for running each service
without Docker. The `synthflow init` wizard described below — pick outputs,
generate a Docker Compose file, start only what you selected — is the Phase 5
target; today, `docker compose up` is the whole setup story.

## Contributing

This project is just getting started and is open to contributors. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
