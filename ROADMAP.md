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
- [x] Stateful entities: define allowed state transitions, generation respects
      them — a `Workflow` (states + initial states + transitions) attaches to
      one field; generation takes a random walk over the graph from a random
      initial state (bounded, early-stopping) instead of picking a value
      independently, and exposes the walk as `<field>_history` alongside the
      field's final value
- [x] Workflow / state machine builder UI — plain field-select + comma-list +
      "source -> target" textarea form, not the React Flow visual canvas from
      the spec (later polish pass, see TODO.md)
- [ ] Generated-field and auto-increment field support

## Phase 3 — Outputs

Goal: generated data can leave the platform through more than a JSON blob.

- [x] Plugin manager: register/enable/disable output plugins per project —
      scoped to what's honest for now: outputs are "enabled" by creating a
      row in their own typed table (`DatabaseConnection`, `RestOutput`) and
      "disabled" by deleting it, with `GET /projects/{id}/outputs` as a
      read-only unified view across them. Not a dynamic third-party plugin
      system yet (see 6. Plugin-Based Architecture in the spec — that's a
      Phase 5 concept, community-authored plugins loaded at runtime); this
      is the "one project, several first-party output kinds" version of it.
- [x] REST output (expose generated data as an API) — `RestOutput`: a public,
      unauthenticated, unguessable-token URL (`GET /public/rest/{token}`)
      that generates a fresh batch for one entity per request, respecting
      its rules/workflows. No auth, no snapshot/caching — the token itself
      is the access control, the same trust model as a webhook URL.
- [x] File outputs: CSV, JSON, Excel — CSV/JSON existed per-entity since Phase 1;
      this phase added Excel (single entity, and a multi-sheet workbook — one
      sheet per entity — at the project level) and extended CSV to the
      project level as a zip of per-entity files (CSV has no multi-table
      concept, so a zip is the honest shape). Excel intentionally includes
      extra generation-time columns like a workflow field's `<field>_history`
      that CSV drops, since CSV is a strict fixed-column format and Excel
      isn't.
- [x] Database connectors: PostgreSQL — a per-project `DatabaseConnection`
      (host/port/credentials, password write-only and stored unencrypted —
      documented, not hidden) plus test-connection and push-generated-rows
      actions; table/column creation goes through SQLAlchemy Core with
      validated identifiers, never string-formatted SQL. MySQL/MongoDB are
      modeled (`DatabaseDialect`) but rejected at push time until those
      drivers are added — same "model it, implement what's tested" approach
      as `many_to_many` in the relationship builder above.
- [ ] Kafka producer output
- [ ] MQTT publisher output
- [x] WebSocket streaming output — `WebSocketStream`: `WS /public/stream/{token}`
      pushes a fresh batch every `1/events_per_second` for as long as a
      client stays connected. Deliberately connection-scoped rather than a
      persistent background producer — the production loop *is* the
      WebSocket handler's loop, so there's no "running" state to persist or
      leak across a backend restart. Kafka/MQTT don't get this for free:
      a broker has no equivalent client connection to hang the loop on, so
      they'll need a real background-task execution model instead — not
      started yet, see TODO.md.
- [x] Output configuration UI (pick + configure one or more outputs per
      project) — a card per output kind on the entity/project pages
      (Database connections, REST output, Live stream), each with its own
      add/list/delete; no single unified "pick your outputs" screen yet,
      but every output type built so far is configurable and usable from
      the UI, not API-only.

## Phase 4 — Advanced Simulation

Goal: data behaves over time, not just at generation time.

- [x] Trend engine: linear, seasonal, cyclic, random walk, exponential, logistic
      — a `Trend` attaches to one numeric field; its value is a function of
      the row's 0-indexed position within the *current batch* (resolved
      design question: position resets every `generate` call rather than
      persisting across a WebSocket stream's ticks — see Trend's docstring
      for why, and what that means for streaming specifically). `increasing`/
      `decreasing` from the spec aren't separate types — they're `linear`
      with the slope's sign, a deliberate consolidation of two labels that
      were the same math.
- [x] Correlation engine (same-entity): link fields so one signal drives
      another — turned out to already be 90% built. A formula field can
      already reference any earlier-ordered field on its own row; the only
      real gap was that formulas were fully deterministic, so a "correlated"
      field came out as a dead-flat line. Closed by adding two functions to
      the shared expression evaluator (`app/services/expressions.py`):
      `noise(stddev)` (gaussian) and `uniform(low, high)`, so
      `humidity = 100 - temperature * 1.5 + noise(3)` gives a real, scattered
      correlation, not new backend machinery. Cross-entity correlation
      ("Stock A ↑ → Stock B ↑" where A and B are different entities) is not
      covered — merged into the cross-entity-rules backlog item, since both
      need the same underlying extension (a formula/rule seeing another
      entity's already-generated data, not just its own row).
- [x] Probability engine: weighted categorical generation — `EntityField.enum_weights`,
      an optional array parallel to `enum_values` (`None` keeps the prior
      uniform `random.choice`; present, it's `random.choices(..., weights=...)`).
      Validated server-side (matching length, non-negative, at least one
      positive) both at field-create/update time and reused as-is by the
      formula/rules/relationships/workflow machinery already built — no
      changes needed there, since weighting only changes how one value is
      picked, not the row-building pipeline around it.
- [ ] Event triggers: threshold-based actions (e.g. `temp > 80 → fire alert`)
- [x] Error injection: missing values, duplicate IDs, corrupted payloads, invalid
      formats — an `ErrorInjection` attaches to one field (same per-field
      pattern as Rule/Workflow/Trend) with a `rate` (0–1) and a set of
      `error_types`: `null`, `empty`, `duplicate`, `truncate`, `wrong_type`,
      `out_of_range`. Corruption is applied in `_corrupt_value` *after* a
      field's value is otherwise fully computed — formula, trend, workflow,
      or plain random — so it doesn't care how the clean value was produced,
      only replaces it on some rows. `duplicate` copies the previous row's
      already-generated (and possibly already-corrupted) value for that
      field, which is why it needs `previous_row` threaded through
      `generate_rows`'s loop; the first row in a batch has no previous row,
      so it keeps its own value. Type-appropriate restrictions are validated
      at creation time (e.g. `truncate` only makes sense for strings,
      `out_of_range` only for numeric fields — see
      `app/services/error_injection.py`). Documented, deliberately
      unresolved interaction: a rule evaluates the row *after* corruption, so
      a rule constraining the same field can discard every corrupted row a
      config produces, once the retry budget (`MAX_RULE_ATTEMPTS`) is spent —
      this is a known tradeoff of reusing the existing discard-and-retry rule
      mechanism rather than a bug to special-case away. Delayed/out-of-order
      events and timeouts are not covered here — those are properties of a
      *stream*, not a single row's value, and belong with the eventual
      Kafka/MQTT background-producer work instead.
      Random failures (whole-request/whole-batch failure, as opposed to a
      bad value within an otherwise-successful row) are also out of scope
      here for the same reason.
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
