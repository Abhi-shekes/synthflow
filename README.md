# SynthFlow

**Open-source synthetic data simulation platform.**
Design realistic data. Simulate real-world behavior. Deliver it anywhere.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-Next.js-black)
![Docker](https://img.shields.io/badge/deploy-Docker%20Compose-2496ED)

![The SynthFlow system map](docs/screenshots/05-system-map-canvas.png)

---

## Contents

- [Why SynthFlow](#why-synthflow)
- [What it does](#what-it-does)
- [Quickstart](#quickstart)
- [**The guided tour**](#the-guided-tour) — every screen, step by step
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Optional services](#optional-services)
- [Using SynthFlow from CI](#using-synthflow-from-ci)
- [Production deployment](#production-deployment)
- [Project status](#project-status)
- [Contributing](#contributing)

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
- **Templates** — eleven ready-made projects for banking, stock market, smart city,
  weather, hospital, manufacturing, CCTV, logistics, GPS fleet, retail, and IoT
- **Live monitoring** — events/sec, active streams, resource usage, error rates

## Quickstart

```bash
git clone https://github.com/Abhi-shekes/synthflow.git
cd synthflow
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

| Service | URL | Notes |
|---|---|---|
| Frontend | [localhost:3000](http://localhost:3000) | the UI shown throughout this README |
| Backend API | [localhost:8001](http://localhost:8001) | interactive docs at `/docs` |
| Grafana | [localhost:3001](http://localhost:3001) | only with the `monitoring` profile |

That's a three-container stack — frontend, backend, Postgres. Everything else
(Kafka, MQTT, MySQL, Mongo, Grafana) is opt-in; see
[Optional services](#optional-services).

---

## The guided tour

Every screenshot below was captured against a real running instance at
1440×900, on a Banking-template project, not mocked up. For the same walkthrough
in more depth, see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

### Step 1 — Sign in, or create an account

Sign up with an email and a password (8+ characters). If your organization has
single sign-on configured, a **Sign in with single sign-on** button appears on
the sign-in page automatically — nothing to enable.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/01-login.png" alt="Sign in page"></td>
<td width="50%"><img src="docs/screenshots/02-signup.png" alt="Sign up page"></td>
</tr>
<tr>
<td width="50%"><em>Sign in — with the SSO button present.</em></td>
<td width="50%"><em>Sign up — a new account always lands on the welcome flow next.</em></td>
</tr>
</table>

### Step 2 — Pick a starting point

The first thing a new account sees. Three ways in, side by side — none of them
is wrong, and you can change course later.

![Welcome flow with three ways to start](docs/screenshots/03-welcome.png)

- **Start blank** — an empty project, if you already know the entities you want.
- **Import an existing schema** — from a SQL file, a JSON Schema document, a live
  database connection, or a sample data file (CSV/Excel/JSON).
- **Use a starter template** — eleven ready-made domains, each pre-populated with
  realistic entities, relationships, and simulation config. This tour uses **Banking**.
- **Skip for now**, top right, to land on an empty `/projects` page instead.

### Step 3 — Read the system map

The home page of every project: your entities, how they relate, and where their
data goes. It has two views, toggled at the top right.

**List view** — the default, scannable, what you want while getting oriented.
The "This is the system map" banner appears only on your first visit.

![System map, list view, with the first-time coach mark](docs/screenshots/04-system-map-list-guided.png)

**Canvas view** — the same information as a pan/zoom diagram, each entity drawn
as a "core sample": a stack of coloured bands, one per field, so you can read an
entity's shape without opening it.

![System map, canvas view](docs/screenshots/05-system-map-canvas.png)

> **Click any entity**, in either view, to open and edit it. **Add an entity**
> (bottom left) and **Add relationship** (bottom right) build the map out;
> **Export** downloads the whole schema as a portable file.

### Step 4 — Find your way around projects

`/projects` lists everything you own or have been shared. A first-time account
also gets a **Getting started** checklist — a progress tracker, not a gate. It
ticks off automatically as you work, and dismissing it is permanent.

![Projects page with the getting-started checklist and starter templates](docs/screenshots/06-projects-checklist-templates.png)

Every starter template stays available here, not just during your first session.

### Step 5 — Design an entity: **Shape**

Clicking an entity opens the **Strata Inspector** — everything about that entity
in four layers, ordered the way data actually moves through the engine:

```
Shape  →  Behaviour  →  Distortion  →  Delivery
fields    rules,         error         where the
types     trends,        injection     rows go
formulas  workflows
```

![Entity page, Shape layer open](docs/screenshots/07-entity-page-guided.png)

- **Shape** is always open — it's the one layer every entity needs.
- The **live specimen**, top right, regenerates as you edit. Change a field and
  the sample rows update without clicking Generate.
- **Behaviour** and **Distortion** collapse to a one-line summary while empty. If
  a template already configured them, they open automatically — nothing pre-built
  ever hides.

Jargon carries a small **ⓘ** that opens a plain-language definition on click:

![A glossary popover explaining quasi-identifiers](docs/screenshots/08-glossary-popover.png)

### Step 6 — Give it **Behaviour**

Rules, event triggers, workflows, trends, lookups, and geo routes. All optional —
Shape is the only required layer.

![Behaviour layer expanded, showing rules, triggers, workflows and trends](docs/screenshots/09-entity-behaviour-expanded.png)

- **Rules** reject any generated row that fails a condition you write (`age >= 18`).
- **Trends** make a numeric field follow a shape over time — rising, cycling,
  drifting — instead of being purely random. The chart under each trend shows you
  the curve before you commit to it.
- **Workflows** move a record through defined states rather than re-rolling it.

### Step 7 — Choose a **Delivery** target

Where the entity's rows go. REST and the **Generate** panel are visible up front;
the other six protocols (WebSocket, Kafka, RabbitMQ, webhook, MQTT, plugin) sit
one click behind **Advanced delivery**, so the common case isn't buried under six
things most people won't need today.

![Delivery layer, REST visible and six other protocols collapsed](docs/screenshots/10-entity-delivery-guided.png)

### Step 8 — Generate rows and inspect them

**Generate** produces rows on demand and shows them in a table on the page. The
same rows feed the **Download CSV** / **Download Excel** buttons beside it.

![Generated rows in a table, with the live specimen showing error injection](docs/screenshots/11-entity-generate-rows.png)

> Look at the **live specimen** on the right: two rows struck through in red.
> That's **Distortion** — deliberately corrupted rows — changing the sample in
> real time, so you can see exactly what "bad data" will look like before it
> reaches anything downstream of you.

### Step 9 — Switch from Guided to Advanced

Every new account starts in **Guided** mode; the collapsed layers and simplified
delivery view above are what that mode looks like. Nothing is deleted or locked —
everything is one click away.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/12-entity-page-full.png" alt="Full entity page in Guided mode"></td>
<td width="50%"><img src="docs/screenshots/13-entity-page-advanced.png" alt="The same entity page in Advanced mode"></td>
</tr>
<tr>
<td width="50%"><em><strong>Guided</strong> — layers collapse until you need them.</em></td>
<td width="50%"><em><strong>Advanced</strong> — every layer and protocol expanded at once.</em></td>
</tr>
</table>

Flipping the toggle at the bottom of the left rail also promotes **Data & jobs**,
**Live monitor**, and **Governance** to permanent rail entries instead of hiding
them behind **More**. Your choice persists across sessions and devices, and never
changes what you *can* do — only what's visible by default.

### Step 10 — Run generation at scale: **Data & jobs**

Everything about *running* generation rather than *designing* a schema.

![Data and jobs page](docs/screenshots/14-data-jobs.png)

- **Generation jobs** run in the background and stream rows straight to a file —
  use these instead of the Generate button for millions of rows or a scheduled run.
- **Record stores** are what make two separate generation calls relate to each
  other, so "customer #42" still exists tomorrow and can place a second order
  instead of every call producing an unrelated batch.
- **Database connections** write rows directly into Postgres/MySQL/MongoDB.

### Step 11 — See every output in one place

The project-wide, read-only answer to "where does this project's data actually
go?" — instead of opening each entity in turn.

![Delivery aggregate page, empty state](docs/screenshots/15-delivery-aggregate.png)

This project has no outputs configured yet, so it shows the empty state. Add a
REST endpoint or Kafka topic on any entity and it appears here, grouped by kind.

### Step 12 — Watch it run: **Live monitor**

Real-time throughput for the whole running system, updating every couple of
seconds without a refresh.

![Live monitor page](docs/screenshots/16-monitor.png)

- Numbers are **process-wide**, not per-project — the metrics are deliberately
  unlabelled by project so that scraping them can never leak a schema.
- **Generation, cumulative** breaks totals down by source (API, REST, WebSocket,
  Kafka, MQTT, plugin, direct database push) since the process started.
- **Process** shows resident memory, CPU time, open file handles, and uptime —
  enough to catch a leak or a stuck producer before it becomes an incident.

### Step 13 — Govern the project

Who can see it, what changed, and how to get back — the three things you reach
for when something has gone wrong, kept together rather than scattered.

![Governance page: sharing, version history, and activity](docs/screenshots/17-governance.png)

- **Sharing** — a project is personal until you explicitly share it into an
  organization. Sharing changes who can see it, never how it behaves.
- **Version history** — snapshots of the project's *design* to diff against or
  roll back to. Not a backup of generated data.
- **Activity** — every change, and whether it came from a browser session or an
  API key. Reads are never recorded.

### Step 14 — Set up the workspace

Three pages that live outside any single project.

<table>
<tr>
<td width="33%"><img src="docs/screenshots/18-api-keys.png" alt="API keys page"></td>
<td width="33%"><img src="docs/screenshots/19-organizations.png" alt="Organizations page"></td>
<td width="33%"><img src="docs/screenshots/20-activity.png" alt="Workspace-wide activity page"></td>
</tr>
<tr>
<td width="33%"><em><strong>API keys</strong> — read-only or full, revocable, shown once. For CI.</em></td>
<td width="33%"><em><strong>Organizations</strong> — shared workspaces with a role ladder.</em></td>
<td width="33%"><em><strong>Activity</strong> — the audit log across every project you can see.</em></td>
</tr>
</table>

### Step 15 — Get help without leaving the page

The **?** in the header explains what the current page is for, the two or three
things people usually do there, and any jargon specific to it.

![Context help panel open on the system map](docs/screenshots/21-help-panel.png)

For the full reference — every page, plus every term in the product with a
one-line definition and an example — open `/learn`:

![The Learn page](docs/screenshots/22-learn-page.png)

And once the app is familiar, **⌘K** (**Ctrl+K** on Windows/Linux) searches
projects, pages, entities, and fields by name from anywhere:

![Command palette open, searching](docs/screenshots/23-command-palette.png)

### Step 16 — Make it yours: light and dark

SynthFlow defaults to dark, but light is a fully designed second theme rather
than an inverted afterthought. Switch with the sun/moon/monitor toggle in the
left rail; **Monitor** follows your OS setting.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/24-light-theme-system-map.png" alt="System map in light theme"></td>
<td width="50%"><img src="docs/screenshots/25-light-theme-monitor.png" alt="Live monitor in light theme"></td>
</tr>
<tr>
<td width="50%"><em>System map, light theme.</em></td>
<td width="50%"><em>Live monitor, light theme.</em></td>
</tr>
</table>

---

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
deployment doesn't pull in Kafka, MongoDB, or MQTT dependencies.

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
| Auth | JWT, OIDC single sign-on, API keys |
| Containers | Docker, Docker Compose |

## Optional services

Extras sit behind Compose profiles, so the default `docker compose up` stays a
three-container stack. Either pick them with the wizard:

```bash
synthflow init                                     # interactive
synthflow init --services kafka,monitoring --yes   # or not
docker compose build backend && docker compose up -d
```

`synthflow init` writes a single `.env` with `COMPOSE_PROFILES` (which services
start) and `SYNTHFLOW_EXTRAS` (which optional Python dependencies go into the
backend image). That second one is what makes the install genuinely modular — a
Kafka-only install never pulls `aiomqtt` at all, and the UI greys out the MQTT
output and tells you how to enable it.

Or turn profiles on directly, without the wizard:

```bash
docker compose --profile monitoring up -d   # Prometheus + Grafana + Loki
docker compose --profile kafka up -d        # Redpanda, for Kafka outputs
docker compose --profile mqtt up -d         # Mosquitto, for MQTT outputs
docker compose --profile mysql up -d        # a MySQL server to push into
docker compose --profile mongo up -d        # a MongoDB server to push into
```

The `mysql` and `mongo` profiles start throwaway *push targets* — servers
SynthFlow writes into, not part of SynthFlow itself. They use non-default host
ports (3307 and 27117) so they don't collide with a database you already run.

With the `monitoring` profile up, Grafana is at
[localhost:3001](http://localhost:3001), already provisioned with a **SynthFlow
overview** dashboard: rows/sec by source, active producers and connected clients,
backend CPU/memory, generation latency, and errors. No login is needed to *view*
it — anonymous visitors get read-only access, and `synthflow init` generates a
real admin password (`GRAFANA_ADMIN_PASSWORD` in `.env`) for editing dashboards
or adding data sources. The backend exposes raw metrics at `/metrics`, and
container logs land in Loki.

See `backend/README.md` and `frontend/README.md` for running each service
without Docker.

## Using SynthFlow from CI

Create a read-only or full **API key** (Step 14 above), then let a pipeline call
the same API the UI uses. `synthflow check` generates rows, runs the quality
report against them, and exits non-zero when it fails — so it works as a gate:

```bash
synthflow check \
  --url https://synthflow.internal \
  --token "$SYNTHFLOW_API_KEY" \
  --project "$PROJECT_ID" \
  --entity "$ENTITY_ID" \
  --count 5000 \
  --assert 'balance >= 0' \
  --assert 'opened_at <= closed_at'
```

| Exit code | Meaning |
|---|---|
| `0` | every check and assertion passed |
| `1` | the report ran and something failed |
| `2` | the report couldn't run (unreachable host, bad token, HTTP error) |

Add `--json` to print the raw report instead of the human summary — useful for
archiving as a build artifact. The report covers what the engine discarded,
where output contradicts its own field definitions, and your own assertions.

## Production deployment

`docker-compose.yml` is a *development* stack: bind-mounted source, hot reload,
and credentials that default to something typeable so a fresh clone runs with
zero setup. None of that belongs on a server.

`docker-compose.prod.yml` is the alternative — real multi-stage images
(`backend/Dockerfile.prod`, `frontend/Dockerfile.prod`, non-root, no dev server),
no bind mounts, and no defaults for anything secret:

```bash
synthflow init --services monitoring --yes   # or whichever profile mix you want
# Put the values it asks for — SECRET_KEY, POSTGRES_PASSWORD,
# NEXT_PUBLIC_API_URL, CORS_ORIGINS — in .env; see docker-compose.prod.yml
# for exactly which ones are required and why.
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

A few things a real deployment still has to decide for itself, since they depend
on where it's actually running:

- **TLS** — put a reverse proxy in front. `BIND_ADDRESS` defaults every port to
  `127.0.0.1` on purpose, so nothing is reachable until you deliberately expose it.
- **Which optional services** it actually needs (mysql/mongo/rabbitmq/minio/
  Grafana/Dex), each hardened the same way: generated password, loopback by default.
- **Backups** for the `synthflow_postgres_data` volume.

## Project status

**Phases 1–5 and 7–14 are live**, backend and frontend, each verified end to end
rather than only by test suite:

| Phase | What landed |
|---|---|
| **1–2** | core platform, relationships, rules, formulas, stateful workflows |
| **3** | outputs: CSV/JSON/Excel, PostgreSQL push, REST, WebSocket, Kafka, MQTT |
| **4** | advanced simulation: trends, probability, error injection, lookup tables, event triggers, timeline replay, geo routes, log/security presets |
| **5** | extensibility: generator/rule-function/output plugins, project export–import, 11 starter templates, a monitoring dashboard, modular install |
| **7** | schema import — build a project from a live database, SQL dump, JSON Schema/OpenAPI, or a sample file |
| **8** | scale: streaming generation with no memory ceiling, a Postgres-backed job queue with progress and cancellation, cron schedules, and background producers that survive a restart |
| **9** | learn from real data: upload sample files and get fitted distributions, observed category frequencies, per-column missing-value rates, and correlations — as an ordinary editable project, using statistics rather than a language model |
| **10** | privacy: personal data detected and replaced with synthetic generators during profiling (so no value from your file reaches the project), k-anonymity and l-diversity measured on generated output, and connection passwords encrypted at rest |
| **11** | data quality: a report on what was actually generated, in the browser and as `synthflow check`, which exits non-zero so it works as a CI gate |
| **12** | connectors, both directions — see below |
| **13** | temporal continuity — see below |
| **14** | teams and governance — see below |

**Phase 12 — connectors, in both directions.** MySQL and MongoDB push alongside
PostgreSQL, S3-compatible object storage (AWS S3, MinIO, R2, Spaces, B2),
Parquet/ORC/Avro job formats, RabbitMQ and a signed webhook — and matching
*input* connectors, so profiling can learn from a URL, a bucket object, or a
database table. Each is an optional extra, so an install only carries the drivers
it uses. Reading a table keeps its real column types, which a CSV export would
flatten to strings. Warehouses (ClickHouse, Snowflake, BigQuery) are the one
bullet not done.

**Phase 13 — temporal continuity.** A **record store** keeps an entity's records
between generation calls, so the same customer exists tomorrow and can receive
new orders. Trends and geo routes continue from where the last call stopped
instead of replaying. A per-store **change log** records inserts, updates and
deletes with `before`/`after` for a CDC consumer to read from a cursor;
slowly-changing-dimension type 1 and 2 make the store a queryable dimension
table; and a **backfill** produces a historical window that live generation then
continues from. `many_to_many` finally emits a real join table.

**Phase 14 — teams and governance.** **API keys** so CI can call SynthFlow at all
(read-only or full, revocable, shown once), **organizations** with a
viewer/member/admin/owner role ladder and projects shared into them, an **audit
log** of every change and who made it — derived from the request, so nothing can
be forgotten — **single sign-on over OIDC**, and **project version history** with
a structural diff and a rollback that snapshots what it replaced. SAML is
deliberately not implemented; see the roadmap.

Phase 6 (the optional AI layer) is deliberately unstarted — nothing depends on
it. Phases 15–16 are planned.

## Contributing

This project is just getting started and is open to contributors. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
