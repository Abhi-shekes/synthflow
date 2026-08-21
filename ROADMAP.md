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
- [x] Event triggers: threshold-based actions (e.g. `temp > 80 → fire alert`)
      — `EventTrigger` is entity-scoped like `Rule` (not field-scoped like
      Trend/Workflow/ErrorInjection/LookupAttachment), holding a `label`
      and the same kind of boolean `condition` a Rule uses, validated the
      same way (evaluated against dummy field values at creation time).
      Resolved design question, called out explicitly in TODO.md before
      starting: what does "firing" mean without a notification system yet?
      Answer — a satisfied trigger doesn't discard/regenerate the row the
      way a Rule does; it's additive, not a filter. Every trigger that
      matches has its `label` appended to that row's `_triggered_events`
      list, a sibling to a Workflow field's `<field>_history` — present in
      JSON/Excel output, dropped from CSV the same way `_history` already
      is (CSV has no place for a variable-length array column), and only
      added at all when the entity has at least one trigger configured.
      No email/Slack/webhook fires; sending a real external notification is
      future work once there's a reason to build that delivery mechanism.
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
- [x] Timeline replay: replay a historical dataset as a live stream at N×
      speed — `TimelineReplay` is project-scoped (like `DatabaseConnection`/
      `LookupTable`) and reuses `LookupTable`'s existing upload/parsing
      instead of inventing a separate "historical dataset" concept: a
      timeline replay's source data and a lookup table's reference data are
      the same shape of thing (project-level uploaded CSV/Excel/JSON), just
      consumed differently — one is sampled from at generation time, the
      other is walked in order against a clock. `WS /public/replay/{token}`
      sends one row per tick (not a batch — replay is inherently row-by-row,
      unlike `WebSocketStream`'s independent random batches), sorted
      ascending by a configured `timestamp_column` (ISO-8601, validated
      against every row at creation time, not spot-checked) regardless of
      upload order, timed by the gap between consecutive rows' timestamps
      divided by `speed_multiplier`, clamped to `[0, 30]` seconds so a huge
      gap doesn't stall the stream and a tiny/negative one doesn't spin.
      After the last row, playback loops back to the first — the negative
      delta this produces is clamped to 0 by the same clamp, an instant
      restart with no special-casing needed. Connection-scoped like
      `WebSocketStream` (no persisted "running" state), but the schedule is
      loaded once per connection rather than re-queried every tick — unlike
      a fresh random batch, replayed historical data doesn't change once
      uploaded, so there's no "did the config change" reason to hit the
      database again on every row. Appears in the `/outputs` aggregate
      alongside the other three output kinds.
- [x] Lookup tables: import CSV/Excel/JSON as reference data — `LookupTable`
      is project-scoped (uploaded once, reusable across every entity in the
      project, matching how `DatabaseConnection` is project-scoped rather
      than per-entity); a `LookupAttachment` then attaches one field to one
      column of one table, the same per-field pattern as Rule/Workflow/
      Trend/ErrorInjection. Parsing (`app/services/lookup_tables.py`)
      dispatches on file extension (.csv/.xlsx/.xls/.json), caps row count
      at `settings.MAX_LOOKUP_ROWS`, and best-effort coerces CSV/Excel's
      text-only cells to int/float (JSON keeps its native types as-is).
      Resolved design question: rather than inventing a new "sample from a
      table" generation path, a lookup-attached field's column values are
      fed into the exact same `fk_pools` mechanism a `Relationship`'s
      foreign-key field already uses (`generate_rows`'s `fk_pools` param;
      see `app/services/generator.build_lookup_pools`) — `field.unique`
      controls with/without-replacement the same way it does for a
      relationship. Because that pool doesn't need another entity generated
      first (the reference data already exists at upload time), a lookup
      works from single-entity generation too, not just project-wide
      generation — a real capability advantage over relationships, not just
      an implementation shortcut. If a field somehow gets both a
      `Relationship` and a `LookupAttachment`, the lookup pool wins (dict
      merge order in `generate_project`) — not cross-validated against each
      other, consistent with Trend/Workflow also not being cross-validated.
      Deleting a `LookupTable` cascades to its attachments via an
      ORM-level `cascade="all, delete-orphan"` rather than relying only on
      the FK's `ondelete=CASCADE`, since SQLite (local dev/tests, unlike the
      Postgres default in docker-compose) doesn't enforce FK constraints
      without a PRAGMA this app doesn't set.
- [ ] Geographic simulation: GPS routes, speed, stops, traffic, delivery vehicles
- [x] User behavior simulation: login/logout/search/click/scroll/cart/purchase
      funnels — turned out to already be exactly what a `Workflow` produces:
      a linear chain of states (e.g. `landing -> search -> cart -> checkout
      -> purchase`) with a random walk that stops early is already a funnel
      with realistic drop-off, no new concept needed. The one real gap: a
      single flat `WORKFLOW_STOP_PROBABILITY` applied at every step
      regardless of state, so every funnel stage lost the same fraction of
      sessions — wrong, since real drop-off is asymmetric (checkout
      abandons far more than an early browsing click). Closed with two
      small, backward-compatible additions to `Workflow`: an optional
      `weight` per transition (`app/schemas/workflow.py`'s
      `WorkflowTransition`, default 1.0/uniform, for picking among a
      branching state's several outgoing edges) and an optional
      `stop_probabilities: dict[str, float]` mapping a state to its own
      stop chance, overriding the global default for that state only —
      states without an entry behave exactly as before. Neither changed the
      DB shape of `transitions` (still schema-flexible JSON, `weight` is
      just an optional key within each edge dict already stored there);
      only `stop_probabilities` needed a migration. `_generate_state_walk`
      in `app/services/generator.py` now resolves both per step, defaulting
      to the old uniform/flat behavior when unset.
- [x] API behavior simulation: status code mixes, latency, timeouts for frontend testing
      — turned out to need almost no new machinery, the same "check
      existing infra first" result as correlation and lookup tables.
      Latency is just a FLOAT field with `min_value`/`max_value`; timeouts
      are `ErrorInjection`'s existing `out_of_range` type pushing latency
      past `max_value`; a status code *mix* is a weighted `ENUM` field
      (`enum_values` + `enum_weights`, already built for the probability
      engine). The one real gap: `enum_values` are always configured as
      strings (`EntityField.enum_values: list[str]`), so a status-code enum
      like `["200", "404", "500"]` was coming out of generation as the
      *string* `"200"`, not the int `200` — wrong for a field meant to look
      like a real HTTP status code. Closed by reusing
      `app.services.lookup_tables.coerce_numeric` (already built for
      CSV/Excel cell parsing, renamed from `_coerce` to make it shared
      infrastructure) in the `ENUM` branch of `_generate_value`: a chosen
      enum value that looks numeric comes out as a real int/float, anything
      else stays a string. No schema change, no new model — one function
      reused in one more place.
- [x] Log generators: Kubernetes, Docker, Nginx, Linux, application logs
- [x] Security event generator: SQLi, brute force, DDoS, port scan, failed login,
      malware events (for defensive tooling / detection testing only) —
      both bullets share one mechanism rather than being two separate
      engines: `EntityField.preset` (a plain nullable string, validated
      against `LogPreset` the same way `regex` already is, not a DB-level
      enum column) picks one of eleven canned single-line generators in
      `app/services/log_generators.py` — five log formats (nginx access,
      docker, kubernetes event, linux syslog, generic application log) and
      six security-event formats (failed login, brute force, SQLi attempt,
      DDoS, port scan, malware alert). Resolved design question: this is a
      STRING-field generation mode, not a new model/table or engine — it
      slots into `_generate_value` exactly where `regex` already does
      (`app/services/generator.py`), so `unique`, `nullable`, and CSV/Excel
      export all keep working with zero extra code, the same "extend the
      existing per-type generator, don't invent a new concept" call already
      made for correlation and lookup tables. `preset` and `regex` are
      mutually exclusive (`preset` fully determines the value) — validated
      in `entities._validate_preset`, the same shape as the existing
      `_validate_enum_weights` check. Every value is fabricated by Faker
      plus randomized timestamps/IPs/ports; nothing here parses real logs
      or executes real attack traffic — the security presets exist purely
      to give detection tooling and dashboards synthetic events to test
      against, the same defensive framing as `error_injection.py`.

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
