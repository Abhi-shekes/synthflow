# Roadmap

SynthFlow is built in six phases. Each phase is expected to ship as a usable
increment — later phases build on a working core rather than waiting for a
"big bang" release. Scope inside a phase may shift; the phase order should not.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase 1 — Core Platform

Goal: a user can sign in, create a project, define an entity by hand, and
generate a batch of fake rows for it.

- [x] Repo scaffolding: `frontend/`, `backend/` (no separate `docker/` — a single
      root `docker-compose.yml` plus a `Dockerfile` per app; `docs/` still open)
- [x] FastAPI backend skeleton (Uvicorn, Pydantic settings, health check route)
- [x] PostgreSQL + SQLite support via SQLAlchemy, Alembic migrations
- [x] JWT authentication (signup, login, refresh, protected routes)
- [x] Project workspace model (a project owns entities; rules/settings/outputs
      arrive in Phase 2/3 as their own engines)
- [x] Entity + field data model (string, int, float, bool, date, datetime, uuid,
      enum, array, object, json) with constraints (required, nullable, unique,
      default, min/max, regex)
- [x] Basic generation engine using Faker, batch mode only
- [x] Next.js frontend skeleton (App Router, Tailwind, shadcn/ui, TanStack Query,
      Zustand, React Hook Form)
- [x] Auth pages + project list/create UI
- [x] Visual schema builder v1 (add/edit/remove entity + fields via forms, no
      drag-and-drop and no relationships yet)
- [x] Docker Compose for local dev (backend, frontend, Postgres)

## Phase 2 — Simulation

Goal: entities can reference each other, carry state, and be shaped by rules
and formulas instead of pure randomness.

- [x] Relationship builder (one-to-one, one-to-many, many-to-many, parent-child,
      foreign keys) + referential generation (e.g. Orders reference real Customers) —
      many-to-many is stored but generated like one-to-many for now; true
      join-table modeling is a later refinement, not blocking
- [x] Rules engine: logical, mathematical, conditional rules — a safe
      restricted-AST expression evaluator (`app/services/expressions.py`, no
      `eval()`) backs per-entity validation rules; a row failing a rule is
      discarded and regenerated. Cross-entity rules (referencing another
      entity's fields, not just this row's) are not yet supported — see
      Notes in TODO.md
- [x] Formula engine: derived/computed fields (`Total = Price × Quantity`) —
      a field's `formula` is evaluated against the row's already-generated
      fields using the same expression evaluator
- [ ] Stateful entities: define allowed state transitions, generation respects them
- [ ] Workflow / state machine builder (visual, React Flow) for non-entity workflows
- [ ] Generated-field and auto-increment field support

## Phase 3 — Outputs

Goal: generated data can leave the platform through more than a JSON blob.

- [ ] Plugin manager: register/enable/disable output plugins per project
- [ ] REST output (expose generated data as an API)
- [ ] File outputs: CSV, JSON, Excel
- [ ] Database connectors: PostgreSQL, MySQL, MongoDB
- [ ] Kafka producer output
- [ ] MQTT publisher output
- [ ] WebSocket streaming output
- [ ] Output configuration UI (pick + configure one or more outputs per project)

## Phase 4 — Advanced Simulation

Goal: data behaves over time, not just at generation time.

- [ ] Trend engine: linear, seasonal, cyclic, random walk, exponential, logistic
- [ ] Correlation engine: link fields/entities so one signal drives another
- [ ] Probability engine: weighted categorical generation
- [ ] Event triggers: threshold-based actions (e.g. `temp > 80 → fire alert`)
- [ ] Error injection: missing values, duplicate IDs, corrupted payloads, invalid
      formats, delayed/out-of-order events, timeouts, random failures
- [ ] Timeline replay: replay a historical dataset as a live stream at N× speed
- [ ] Lookup tables: import CSV/Excel/JSON as reference data
- [ ] Geographic simulation: GPS routes, speed, stops, traffic, delivery vehicles
- [ ] User behavior simulation: login/logout/search/click/scroll/cart/purchase funnels
- [ ] API behavior simulation: status code mixes, latency, timeouts for frontend testing
- [ ] Log generators: Kubernetes, Docker, Nginx, Linux, application logs
- [ ] Security event generator: SQLi, brute force, DDoS, port scan, failed login,
      malware events (for defensive tooling / detection testing only)

## Phase 5 — Extensibility

Goal: the community can extend SynthFlow without forking it.

- [ ] Formal plugin framework (output plugins, rule plugins, generator plugins,
      AI provider plugins) with a documented interface + versioning
- [ ] Generator plugin examples: PAN, VIN, IMEI, GST, QR, email generators
- [ ] Template marketplace format (import/export a project as a shareable template)
- [ ] Starter templates: banking, stock market, smart city, weather, hospital,
      manufacturing, CCTV, logistics, GPS fleet, retail, IoT
- [ ] Live monitoring dashboard: events/sec, active streams, CPU/memory, connected
      clients, errors, output status (Prometheus + Grafana + Loki)
- [ ] Modular installation: `synthflow init` wizard and Web UI service picker that
      only pull/build the plugins actually selected (e.g. Kafka-only install skips
      MQTT/RabbitMQ/GraphQL/MongoDB entirely)

## Phase 6 — AI (optional layer)

Goal: natural-language project generation for users who opt in — the platform
remains fully functional without this phase for anyone who doesn't.

- [ ] BYO-LLM provider integration (OpenAI, Claude, Gemini, Mistral, Groq,
      OpenRouter, Ollama, LM Studio, generic OpenAI-compatible endpoint)
- [ ] Prompt → schema generation
- [ ] Prompt → rules generation
- [ ] Prompt → workflow generation
- [ ] Prompt → full project generation (schema + rules + relationships + workflows +
      simulation settings + output config), with a mandatory human review/diff step
      before anything is applied

---

## Future / not yet scheduled

Ideas worth tracking but not committed to a phase yet:

- Multi-user collaboration on a single project
- Version control for projects (diff/rollback project definitions)
- Project import/export and sharing
- Cloud deployment wizard, Kubernetes deployment
- Public plugin/template marketplace (hosted, not just import/export)
- Reverse-engineer an existing database or API into a SynthFlow project
