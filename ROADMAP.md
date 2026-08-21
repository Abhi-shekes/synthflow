# Roadmap

SynthFlow is built in phases. Each phase is expected to ship as a usable
increment — later phases build on a working core rather than waiting for a
"big bang" release. Scope inside a phase may shift; the phase order should not.

**Phases 1–5 are complete.** Phase 6 (AI) is deliberately optional: nothing
after it depends on it, and the platform stays fully functional for anyone who
never enables it. Phases 7–16 are planned, not started — they are ordered by
dependency and value rather than by ambition, and being further out, their
scope is more likely to move than the earlier phases' was.

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
      discarded and regenerated. Cross-entity rules/correlation (a formula,
      rule, or event trigger referencing another entity's fields via
      `RelatedEntity.field`, not just this row's) shipped later as its own
      backlog item, once entities/relationships/formulas/rules were all in
      place to build on — reused the existing evaluator rather than adding
      a second mechanism: `ast.Attribute` is now allowed, but *only* one
      level deep on a name that already resolves to a plain dict already
      present in `variables` — never real attribute/method access on an
      actual object, so the "no `eval()`" safety property is unchanged.
      The harder part wasn't syntax — it was making sure `Customer.age`
      resolves to the *specific* customer this order's foreign key actually
      points to, not a random customer. `generate_project` now builds a
      `relationship_lookup` (source field name → {fk value → full target
      row}) alongside the existing `fk_pools`, and `_generate_one_row`
      resolves every relationship-sourced FK field in a pre-pass *before*
      its main per-field loop, so the linked row is available to every
      field's formula/rule/event-trigger regardless of declared field
      order. Deliberately project-wide only: a single-entity `generate`
      call has no other entity's rows to draw from, so a cross-entity
      reference there fails with a clear "Unknown variable" 400 rather than
      silently resolving to nothing — the same asymmetry already accepted
      for `Relationship` itself (unlike `LookupAttachment`/`GeoRoute`,
      which work from single-entity generation precisely because they
      don't need another entity's rows).
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
- [x] Generated-field and auto-increment field support — turned out to
      already be fully covered, the same "check existing infra first"
      result as several Phase 4 items. "Generated field" is the existing
      `formula` field (checked above) plus `FieldType.UUID` (Phase 1) for
      generated identifiers. "Auto-increment" is a `Trend` with
      `trend_type=linear`, integer `start`/`slope`, on an INTEGER field —
      `start + slope * position` is already exactly a sequential counter,
      and it's inherently collision-free for integer slope, so it composes
      cleanly with `unique=True` even though the unique-value dedup path
      isn't invoked for trend-driven fields (confirmed by test: 50 rows
      produced exactly `1..50`, all distinct). No backend code changed.
      The one real gap was discoverability, not capability — nothing in
      the UI signposted "linear trend with slope 1" as the way to get an
      auto-increment id — closed with a one-click "Use as auto-increment
      (start 1, step 1)" preset button in the trend dialog.

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
- [x] Kafka producer output / MQTT publisher output — `KafkaOutput` and
      `MQTTOutput`: entity-scoped outputs that stream a fresh JSON message
      per generated row into a real broker topic, one message per row
      (matching TimelineReplay's per-row choice rather than
      WebSocketStream's per-tick array). This is the "real background-task
      execution model" WebSocketStream's docstring had flagged as missing:
      each output is backed by an in-process `asyncio.Task`
      (`app/services/stream_producers.py`) in a module-level registry,
      started from an `async def` create route via `asyncio.create_task()`
      and cancelled from an `async def` delete route — the only async
      routes in the app, since every other route is sync SQLAlchemy.
      Bounded retry with backoff (5 consecutive failures max, 5s backoff,
      5s connect timeout) so a broker outage never hangs a request or spins
      forever. Same honest tradeoffs as WebSocketStream: no persisted
      "running" state and no resume-on-restart (a row surviving a backend
      restart with no live task is a documented gap, not silently papered
      over), single-process only. FastAPI `lifespan` now cancels every
      live producer task on shutdown so nothing outlives the process.
      New optional docker-compose services (`redpanda`, `mosquitto`)
      gated behind Compose profiles (`--profile kafka`, `--profile mqtt`)
      so the default `docker compose up` is unaffected. Verified against
      real brokers, not mocks: produced through the actual UI, then
      consumed 5 real messages off the Kafka topic with a throwaway
      `aiokafka` consumer container and 5 real messages off the MQTT topic
      with `mosquitto_sub` in a throwaway container; separately proved
      `DELETE` actually stops production (not just removes the DB row) by
      comparing the Kafka topic's end-offset immediately after delete and
      again 6 seconds later — unchanged both times.
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
      ("Stock A ↑ → Stock B ↑" where A and B are different entities) shipped
      later as its own backlog item, `RelatedEntity.field` syntax — see the
      Rules engine bullet in Phase 2 for the full writeup.
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
- [x] Geographic simulation: GPS routes, speed, stops, traffic, delivery
      vehicles — the last Phase 4 item, and (per the design note in TODO.md
      before starting) the one genuinely needing new machinery: no existing
      engine produced a 2D path across rows (`Trend` is scalar-only) or let
      a field see the previous row's value in a reusable way. `GeoRoute`
      attaches one OBJECT/JSON field to an ordered waypoint sequence from a
      project-level `LookupTable` — a *third* consumption mode for that
      same upload (`LookupAttachment` samples one value, `TimelineReplay`
      walks in order against a clock, this walks in order across the
      generated batch, interpolated). The field's value becomes
      `{"lat": float, "lon": float}`, linearly interpolated between the two
      waypoints bounding each row's fractional position within the current
      batch (`app/services/geo_routes.generate_geo_point`) — row 0 is the
      route's first waypoint, the last row its last, regardless of how many
      waypoints were uploaded vs. rows requested (a 5-waypoint route
      sampled into 200 rows produces 200 smoothly interpolated points along
      that polyline). Resolved design questions, kept deliberately small:
      "stops" aren't a separate configured concept — upload the same
      waypoint twice in a row in the source data and however many output
      rows land in that now-tiny segment interpolate to essentially the
      same point, a natural consequence of the interpolation rather than a
      special case; speed and traffic aren't built here at all — compose a
      plain FLOAT field (optionally with a Trend, or an ErrorInjection
      `out_of_range` for a "jammed" outlier) the same way latency already
      does for API-behavior simulation, since a route only owns *where*,
      not how fast. "Delivery vehicles" needed no separate mechanism either
      — it's the same route + entity shape, just named for a use case.
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

- [x] Formal plugin framework — generator plugins in this pass, rule-function
      and output plugins added in follow-up passes below; only AI provider
      plugins are still a genuinely unstarted `[ ]` item further down (see
      Phase 6). Real third-party extensibility via Python's
      standard entry-point mechanism (`app/services/plugins.py`): any
      package installed into the backend's environment that declares a
      zero-arg callable under the `synthflow.generators` entry-point group
      is discovered automatically and offered as a `preset` — no SynthFlow
      code change, no registration step beyond `pip install` + a process
      restart (entry-point discovery isn't cached, so nothing else has to
      change; a *running* worker only misses a brand-new install until it
      restarts, which is expected and documented, not a bug). This is a
      real architecture change, not just an additive one: `preset` moved
      from a closed `LogPreset | IdentifierPreset` Pydantic union to a
      plain `str`, validated dynamically against the live registry in
      `entities._validate_preset` instead of a compile-time enum — the
      whole point of a plugin system is that the valid set isn't known
      until runtime. `PLUGIN_API_VERSION = 1` exists for a future breaking
      change to check against; there's nothing to enforce yet. A plugin
      name colliding with a built-in preset is skipped (with a logged
      warning) rather than allowed to shadow it, and a plugin that fails to
      load doesn't take down the others or the app. Security is the same
      "documented, not hidden" trust model as everywhere else in this repo:
      a generator plugin is arbitrary Python code running with the
      backend's own privileges, no sandboxing — the deployer vets what they
      `pip install`, same as any other dependency.
      `examples/example-generator-plugin/` is a real, minimal,
      pip-installable plugin package (a `license_plate` generator) that
      doubles as the "documented interface" the roadmap item calls for and
      as this feature's genuine end-to-end proof: built and installed with
      `pip install -e`, not mocked, into the actual running Docker backend
      container against Postgres. `GET /generator-plugins` is new — the
      frontend's preset picker now fetches presets instead of hardcoding
      `LOG_PRESETS`/`IDENTIFIER_PRESETS` (removed as dead code), so a newly
      installed plugin shows up in the UI without a frontend rebuild; it
      renders as a third `Plugins` group in the Select, only when at least
      one is installed. `entity_fields.preset` widened from `VARCHAR(50)`
      to `VARCHAR(100)` (first `ALTER COLUMN TYPE` migration in the repo —
      needed `op.batch_alter_table` since SQLite, used for local dev/tests,
      has no native `ALTER COLUMN TYPE`; Postgres doesn't need the batch
      wrapper but it's harmless there). 11 new tests (mocking
      `importlib.metadata.entry_points` for discovery/collision/
      broken-plugin/stale-plugin-after-uninstall cases), 187 passed / 3
      skipped total, lint clean. Verified against a real installed package,
      not just mocks: `pip install -e` the example plugin into the live
      backend container, confirmed `license_plate` appears via the API
      after a restart, created a field with it and generated real
      license-plate-shaped rows against Postgres, confirmed the picker's
      new `Plugins` group renders and is selectable in a browser with zero
      console errors, then uninstalled the plugin and confirmed both that
      it disappears from the registry and that a field still referencing
      it now fails generation with a clean 400, not a 500.
- [x] Rule-function plugins — the second half of the plugin framework,
      following the same "check existing infrastructure first" pattern
      that closed out correlation/API-behavior/user-behavior in Phase 4:
      a "rule plugin" isn't a new concept bolted onto `Rule`, it's a new
      capability in the expression evaluator every rule/event-trigger
      condition and formula already runs through
      (`app/services/expressions.evaluate`). Any package installed into
      the backend's environment that declares a callable under the
      `synthflow.rule_functions` entry-point group becomes callable *by
      name* from inside any expression, exactly like the built-in
      `noise()`/`uniform()` already are — `is_business_day(order_date)`
      or `luhn_valid(card_number)`, not just presets. Discovery lives in
      `app/services/plugins.py` next to the generator-plugin mechanism
      (shared `PLUGIN_API_VERSION`, same collision/broken-plugin
      handling), but the two modules stay one-directional
      (expressions.py imports plugins.py, never the reverse) to avoid a
      circular import — `GET /rule-functions` merges the built-in names
      (now exported as `expressions.BUILTIN_FUNCTIONS`) with the plugin
      ones at the route layer instead.

      Building the example rule-function plugin (`is_business_day`,
      added to `examples/example-plugin/` alongside the existing
      `license_plate` generator — renamed from `example-generator-plugin`
      since it now demonstrates both halves of the framework) surfaced a
      real bug, not a hypothetical one: creating a rule/event-trigger/
      formula validates the condition against dummy stand-in values
      first, and every field's stand-in was the integer `1` regardless of
      its real type — so `is_business_day(order_date)` on a DATE field
      raised an unhandled `TypeError` (`date.fromisoformat(1)`) that
      surfaced as a raw 500, not a 400. Fixed two ways: `dummy_row_values`
      (`app/api/routes/entities.py`) now picks a type-appropriate
      stand-in per field (a real ISO date for DATE, an enum's first value
      for ENUM, etc.) so realistic conditions actually validate instead
      of always being rejected or crashing; and `evaluate()`'s function
      call handling now wraps *any* exception a called function raises
      (built-in or plugin) in `ExpressionError`, so a user-authored
      condition can never 500 the server no matter what the function
      does internally — defense in depth, not reliant on the dummy-value
      fix alone.

      13 new tests for the plugin mechanism itself plus 2 regression
      tests for the dummy-value/exception-safety bugs, 227 passed / 3
      skipped total, lint clean. Verified against the real installed
      example plugin, not mocks: `is_business_day` appeared via
      `GET /rule-functions` after a restart, a rule using
      `is_business_day(order_date)` on a DATE field failed to create with
      a 500 *before* the fix and created cleanly *after* it, then
      generating 15 rows against Postgres confirmed every single
      `order_date` really did land on a weekday — the rule's
      discard-and-regenerate loop was genuinely calling the plugin
      function per candidate row, not just accepting the condition
      syntactically. Confirmed in a browser too: the Rules and Event
      triggers cards' helper text now lists `is_business_day` under "From
      installed plugins" with zero console errors. Uninstalling the
      plugin made it disappear from `GET /rule-functions` and a new rule
      referencing it fail with a clean 400.
- [x] Output plugins — the third and final piece of the plugin framework
      (AI provider plugins are the only category left, deferred to
      Phase 6). Unlike Kafka/MQTT (first-party typed models with a fixed
      config shape), an output plugin's config shape isn't known until
      it's installed, so there's one generic `PluginOutput` model
      (`plugin_name` + a free-form JSON `config` column) instead of a new
      typed table per plugin — any package installed into the backend's
      environment that declares a callable under the `synthflow.outputs`
      entry-point group becomes a selectable `plugin_name`, receiving
      `(config: dict, rows: list[dict])` once per tick. The plugin only
      owns delivery; a new generic background loop
      (`app/services/plugin_output_producers.py`, deliberately a sibling
      to `stream_producers.py` rather than a refactor of it — Kafka/MQTT
      keep their own working code untouched) owns pacing and batch
      loading, the same `asyncio.Task`-per-output execution model as
      Kafka/MQTT (not resumed on restart, single-process only, bounded
      retry with backoff). A delivery function can be sync or async — a
      plugin author writing something as simple as "append to a file"
      shouldn't have to know asyncio; SynthFlow runs a sync one in a
      thread so it can't block the event loop.
      `examples/example-plugin/` grew a third entry point,
      `write_jsonl` — a deliberately network-free example (appends each
      generated batch to a local file as JSON lines) so live verification
      didn't need a broker the way Kafka/MQTT's did. `GET /output-plugins`
      lists installed ones; the entity page's new "Plugin output" card
      picks from that list and takes the config as raw JSON, since the
      shape is the plugin's to define, not SynthFlow's.
      8 new tests, including one that doesn't stop at CRUD: a fake
      in-memory plugin function records every batch it receives, and the
      test waits on the *real* background `asyncio.Task` (started by the
      create route) to actually call it with real generated rows before
      asserting — stronger than Kafka/MQTT's tests could be, precisely
      because a plugin output's "broker" is just a Python function, not
      something requiring a live external service inside the test
      environment. 235 passed / 3 skipped total, lint clean. Verified
      against the real installed example plugin: created a `write_jsonl`
      output against Postgres and watched a real file inside the backend
      container fill up with real generated rows honoring the field's
      min/max constraints; separately proved `DELETE` genuinely stops the
      producer the same way as Kafka/MQTT (line count unchanged 4 seconds
      after delete, not just the DB row gone). Confirmed in a browser too:
      the new card's plugin picker, config textarea, and created-output
      list all rendered correctly with zero console errors, and the
      background task it started wrote real rows to a file mid-session.
      Uninstalling the plugin made it disappear from `GET /output-plugins`
      and a new output referencing it fail with a clean 400.
- [x] Generator plugin examples: PAN, VIN, IMEI, GST, QR, email generators —
      `IdentifierPreset` (`app/services/identifier_generators.py`), the same
      "canned generator behind a STRING field's `preset` column" mechanism
      `LogPreset` already established, not a new concept or a real plugin
      system: `pan`/`vin`/`imei`/`gstin`/`qr_code`/`business_email`. Formats
      match the real-world position/charset rules closely enough to pass a
      naive shape check — VIN excludes I/O/Q, IMEI's 15th digit is a real
      Luhn check digit — but GSTIN's checksum char is left random rather
      than guessed at, since that algorithm isn't simple/public like Luhn's
      (documented in the module docstring, same "ship the honest version"
      choice as everywhere else). `qr_code` renders an actual PNG (via the
      new `qrcode[pil]` dependency) encoding a synthetic URL, returned as a
      base64 data URI — the one preset whose value is much longer than
      String(255), so `db_output.py`'s Postgres-push column-type mapping
      now special-cases it to `Text()` instead of truncating. Frontend's
      preset picker is one `Select` with two groups (log/security events,
      identifiers/codes) over the same field, not two mutually-exclusive
      controls, since it's still one string column either way. This is the
      first Phase 5 item shipped, and it confirms the "check existing
      infrastructure first" pattern extends past Phase 4: no new model, no
      schema migration, no new route — just a new enum, a new generator
      module mirroring `log_generators.py`, and a two-place schema/db_output
      update. 9 new tests (including a full Luhn-digit recompute and a real
      PNG-magic-bytes check on the decoded QR image), 176 passed / 3 skipped
      total, lint clean. Verified end-to-end in a browser: a VIN-preset
      field generated 10 rows of real 17-character, I/O/Q-free values with
      zero console errors.
- [x] Template marketplace format (import/export a project as a shareable
      template) — `ProjectTemplate` (`app/schemas/template.py` +
      `app/services/templates.py`): a project's *design* — entities,
      fields, relationships, rules, event triggers, workflows, trends,
      error injections, lookup tables (including their uploaded data,
      inline) and lookup attachments, geo routes — as one JSON document.
      Every reference inside it is by *name*, not database id: entity/
      field ids only mean something inside the project they came from, so
      export rewrites every id to a name-based reference and import
      resolves each one back to whatever row was just created *in this
      import*, not the original. That's also what makes a template
      hand-editable — the future "starter templates" item below is just
      curated JSON files matching this shape, not a database dump.
      Deliberately excludes outputs (`DatabaseConnection`, `RestOutput`,
      `WebSocketStream`, `KafkaOutput`, `MQTTOutput`) and generated data:
      outputs hold deployment-specific secrets/addresses that mean nothing
      to whoever's importing the template, so the recipient wires up their
      own the same way they would for a hand-built project. Import is
      all-or-nothing: nothing is committed until every row resolves
      successfully, so an unknown reference or an invalid enum value (e.g.
      a bad `field_type`) leaves no partial project behind — caught as a
      clean 400, not a 500 or an orphaned row. `GET /projects/{id}/export`
      and `POST /projects/import`; frontend adds an "Export" button on the
      project page (downloads a `<name>.synthflow.json` file) and an
      "Import project" button on the projects list (a file picker feeding
      the same JSON back in) — no new dialog components needed, reusing
      the existing blob-download helper. 8 new tests including a full
      round trip through every attachment type and a project-wide
      `/generate` call on the *imported* project proving the round-tripped
      rules/relationships/workflow/lookup/geo-route config actually still
      works, not just that the JSON shapes match. 195 passed / 3 skipped
      total, lint clean. Verified end-to-end in a browser against the real
      Docker/Postgres stack: created a project through the UI, clicked
      Export, got a real downloaded JSON file, fed it back in through
      Import, saw the project appear a second time with zero console
      errors; separately verified the richer case (relationship + rule)
      against the live API — export, import as a new project, generate 10
      real rows from the *imported* project, all respecting the
      original's constraints.
- [x] Starter templates: banking, stock market, smart city, weather, hospital,
      manufacturing, CCTV, logistics, GPS fleet, retail, IoT — all 11 roadmap
      domains, each a plain `ProjectTemplate` JSON file bundled with the
      backend (`app/starter_templates/*.json`), proving the template format
      really is hand-editable/shareable and not just an export artifact: no
      new model, no new import mechanism — `GET /starter-templates/{key}`
      returns the exact same shape `POST /projects/import` already accepts,
      so "use a starter template" is just "fetch this JSON, then import it,"
      reusing the whole existing pipeline including its validation. That
      validation turned out to have a real gap worth closing first: import
      was resolving references but skipping the type/shape checks each
      dedicated create-route already enforces (a trend on a non-numeric
      field, an error type invalid for its field type, a workflow
      transition to an unmodeled state, enum_weights/preset mismatches).
      Fixed by extracting the shared checks into
      `app.services.field_validation` (reused by both
      `entities.add_field`/`update_field` and template import) and adding
      the same trend/workflow/error-injection/lookup/geo-route validation
      import had been missing — a template that would have silently
      produced broken generation now fails at import time with a clean 400.
      Each starter template exercises a different mix of the simulation
      surface on purpose rather than being minimal: PAN/VIN/IMEI/
      business-email presets, auto-increment trends, a random-walk stock
      price, seasonal weather/traffic curves, weighted enums, regex SKUs,
      branching workflow funnels with `stop_probabilities` (hospital
      admissions, logistics fulfillment, retail checkout), lookup-table
      attachments, and geo-routes. Frontend adds a "Starter templates"
      gallery on the projects list (one card per template, "Use template"
      fetches + imports in one click) — no new dialog components, and
      `ProjectTemplate` picked up an optional `description` used by both
      the gallery cards and any future hand-exported project. 26 new
      backend tests total between the validation-gap fix and the starter
      templates themselves (including one that imports and generates from
      *every* bundled template and checks every declared field actually
      comes back), 212 passed / 3 skipped, lint clean. Verified end-to-end
      in a browser: all 11 cards render with real descriptions, "Use
      template" on GPS Fleet created a real project through the actual UI,
      and generating from its `LocationPing` entity produced real
      interpolated lat/lon points walking the bundled route — the geo-route
      attachment survived the import intact — zero console errors.
- [x] Live monitoring dashboard: events/sec, active streams, CPU/memory, connected
      clients, errors, output status (Prometheus + Grafana + Loki) — all six,
      as a provisioned Grafana dashboard rather than just an exposed
      `/metrics` endpoint: `docker compose --profile monitoring up` and the
      **SynthFlow overview** dashboard is already there at :3001 with both
      datasources wired, no login and no "add a datasource" step.
      Instrumentation is `app/services/metrics.py` (every metric defined in
      one place) plus `prometheus-client`; the stack itself is four
      profile-gated compose services (`prometheus`, `grafana`, `loki`,
      `promtail`) with configs under `monitoring/`, so the default
      `docker compose up` is still the same three containers.

      Two design decisions did most of the work. First, the "active"
      gauges *read existing state rather than counting it*: both
      `stream_producers` and `plugin_output_producers` already keep a
      module-level `_tasks` registry of live background tasks, and that
      registry already **is** the active-producer count — so those gauges
      are `set_function` callbacks over `len()` of it, with zero
      instrumentation added to the producers and no second source of truth
      to drift out of sync. (`stream_producers` gained one small parallel
      `_task_kinds` dict purely so the gauge can split kafka from mqtt; the
      loops never read it.) Connected WebSocket clients is the one real
      inc/dec gauge, because there's no registry there — the handler's own
      stack frame is the state — and its `dec()` sits in a `finally`
      specifically because that loop also exits through two early
      `return`s and through cancellation, any of which would otherwise
      leak the gauge upward forever.

      Second, **every label value is drawn from a fixed hardcoded set**
      (`source` ∈ api/rest/websocket/kafka/mqtt/plugin/database_push,
      `kind` ∈ kafka/mqtt/plugin) — never a project, entity, or field
      name. That's not just Prometheus cardinality hygiene: it's what makes
      serving `/metrics` unauthenticated defensible, since Prometheus
      scrapes on a timer with no way to refresh a JWT. The endpoint exposes
      throughput, latency and error counts and nothing about anyone's
      schema, and there's a test asserting exactly that (generate against
      deliberately distinctive project/entity names, then assert they don't
      appear in the scrape body) so a future entity-labelled metric fails
      loudly instead of quietly leaking. Those label sets are also
      pre-seeded at zero on startup, so an unused output kind reads `0`
      instead of Grafana's "No data".

      Row counting/timing needed real call-site instrumentation, since
      `generate_rows` can't know who's calling it — but rather than thread
      a `source` argument through the generation engine, the *boundary*
      that already knows its own identity wraps the call in a
      `metrics.generation(source)` context manager (timing, row count, and
      error counting in one). `app/services/generator.py` therefore
      contains no metrics code at all; all 8 generation call sites carry it
      instead.

      13 new tests, 248 passed / 3 skipped total, lint clean. Verified
      live against the full 7-container stack, not just unit tests: 100
      rows generated through the real API moved the counter by exactly
      100; Prometheus scraped it (target `up`) and `rate()` computed a real
      non-zero events/sec; Grafana came up with both datasources and all
      12 panels provisioned and could proxy-query Prometheus successfully;
      Loki had real backend log lines. Then the live-state gauges were
      driven for real: a genuine WebSocket client made the connected-client
      gauge go 0→1→0 (proving the `finally`) while counting 10 rows under
      `source="websocket"`, and a Kafka output pointed at a deliberately
      unreachable broker made `active_producers{kind="kafka"}` go 0→1,
      logged 3 delivery errors through the retry/backoff path, then
      returned to 0 on delete. Finally the rendered dashboard was
      screenshotted under sustained mixed load and inspected: 29 rows/sec
      headline, per-source throughput, that producer's 0→1→0 lifecycle
      spike, its errors in red, p95 latency split by source, backend
      CPU/RSS, and live logs — every panel populated, no "No data", no
      console errors.
- [x] Modular installation: `synthflow init` wizard and Web UI service picker that
      only pull/build the plugins actually selected (e.g. Kafka-only install skips
      MQTT/RabbitMQ/GraphQL/MongoDB entirely) — and this one is genuine, not
      cosmetic. Until now `aiokafka` and `aiomqtt` were *core* dependencies,
      so every install pulled both whether or not you'd ever start a
      broker — the exact opposite of modular. They're now optional extras
      (`pip install '.[kafka]'`), which forced three real changes rather
      than a config flag: `stream_producers` imports its broker client
      inside the loop that needs it so the module still imports when
      neither is present; `app/services/install.py` detects availability
      at runtime with `find_spec` (not a real import — this is called per
      request); and the create routes refuse with a 400 that *names the
      extra to install* rather than 500-ing or spawning a background task
      that dies on its first tick.

      `synthflow init` (a real console script, `app/cli.py`) writes one
      `.env` and deliberately does not generate a bespoke compose file:
      Compose already reads `COMPOSE_PROFILES` from `.env` and profiles
      already exist for every optional service, so one variable makes a
      plain `docker compose up` start exactly what you picked — a
      generated second compose file would just be a parallel source of
      truth that drifts. It writes two keys: `COMPOSE_PROFILES` (which
      *services* start) and `SYNTHFLOW_EXTRAS` (which *Python extras* the
      backend image installs, passed through as a Docker build arg). It's
      interactive by default and non-interactive for CI
      (`--services kafka,monitoring --yes`, `--all`, `--none`), rewrites
      only the two keys it owns so re-running can't eat someone's
      `SECRET_KEY`, and finds the repo root by walking up so it works from
      `backend/` too.

      The "Web UI service picker" half is honest about what a browser can
      do: the frontend can't restart Docker for you (and giving it the
      socket would be a serious privilege escalation), so instead
      `GET /install-config` reports what this install actually supports
      and the entity page greys out the Kafka/MQTT cards when their extra
      is missing, naming the `synthflow init` command that enables them —
      a picker that reflects reality rather than a control whose only
      possible outcome is an error.

      19 new tests; the 4 existing broker-output tests became
      `skipif`-gated on their extra, which is itself the feature working.
      Verified in both directions rather than one: with extras removed the
      app imports fine, reports `kafka: False, mqtt: False`, and the suite
      is 263 passed / 7 skipped; with `.[all]` installed it's 267 passed /
      3 skipped and those tests really run. The build arg was verified by
      actually building two images — a core-only image has neither client,
      a `SYNTHFLOW_EXTRAS=kafka` image has aiokafka and genuinely **no**
      aiomqtt while still booting and reporting `mqtt: False`. And the
      wizard was verified end to end: `synthflow init --services
      kafka,monitoring` produced an `.env` that made `docker compose`
      resolve to core + redpanda + the four monitoring services and no
      mosquitto. One real bug surfaced along the way — an idempotency test
      caught the wizard stacking a duplicate banner comment on every
      re-run, fixed by stripping its own marker line as well as the keys.

      **This completes Phase 5.**

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

## Phase 7 — Schema Import

Goal: start from a schema that already exists instead of hand-building every
entity. Today a 40-table application means defining 40 entities by hand; this
turns that into one import and an edit pass.

- [ ] Introspect a live database into a project: tables → entities, columns →
      fields (type, nullability, uniqueness, length/precision), foreign keys →
      relationships. PostgreSQL first, matching the connector already used for
      database push
- [ ] Import from a SQL DDL dump, so no live credentials are needed
- [ ] Import from JSON Schema and OpenAPI, for teams whose contract is the API
      rather than the database
- [ ] Infer a project from a sample data file (CSV/JSON/Parquet) — column types,
      obvious formats, and enum-looking columns
- [ ] Mandatory review/diff step before anything is created, and all-or-nothing
      application on confirm
- [ ] Report what could not be represented (check constraints, computed columns,
      exotic types) rather than importing silently and losing it

      Every importer should produce a `ProjectTemplate` and hand it to the
      existing `POST /projects/import` path rather than writing rows directly —
      that format, its name-based references and its all-or-nothing validation
      already exist from Phase 5, so this phase is mostly new front-ends onto a
      pipeline that is already proven.

## Phase 8 — Scale and Scheduled Jobs

Goal: generate far more than fits in memory, unattended, and survive a restart.
This is the phase that turns SynthFlow from a good interactive tool into
something that can sit inside a real data pipeline.

- [ ] Streaming/chunked generation — write rows out as they are produced instead
      of building the whole batch in memory first, removing
      `MAX_GENERATE_ROWS` as a hard ceiling rather than just raising it
- [ ] A persistent job model: queued/running/succeeded/failed, progress, cancel,
      retry, and a run history with row counts and timings
- [ ] Scheduled runs (cron-style), e.g. refresh a staging database nightly
- [ ] Resume background producers after a restart — closes the gap documented in
      `KafkaOutput`/`MQTTOutput`/`PluginOutput`, where a surviving row currently
      has no running task behind it
- [ ] Distributed locking so a producer runs on exactly one worker — closes the
      "single-process only, multiple workers would duplicate producers"
      limitation documented in `app/services/stream_producers.py`
- [ ] Per-output backpressure and rate limiting, so a slow consumer slows the
      producer instead of building an unbounded queue

      Several later phases assume this exists: Phase 9's profiling and Phase 13's
      historical backfill are both long-running work that wants a job model
      rather than a request/response cycle.

## Phase 9 — Learn From Real Data

Goal: given a real sample, produce statistically similar synthetic data —
the second major mode of synthetic data generation, and the one SynthFlow
currently cannot do at all.

- [ ] Profile an uploaded dataset: per-column type, distribution shape, null
      rate, cardinality, min/max, and recurring string patterns
- [ ] Fit and sample from distributions (normal, lognormal, exponential,
      categorical with observed frequencies) instead of uniform randomness
- [ ] Preserve relationships *between* columns — a copula or equivalent — so
      generated rows keep the correlations the real data had, not just correct
      per-column histograms
- [ ] Infer referential structure across multiple related files, producing
      relationships rather than isolated entities
- [ ] Turn the profile into an ordinary, editable project rather than an opaque
      model, so the inferred distributions can be inspected, corrected and
      version-controlled like anything else

      Deliberately statistics, not language models. Keeping this out of Phase 6
      means it still works in an air-gapped install with no LLM provider
      configured, and means the two can be developed independently.

## Phase 10 — Privacy and Compliance

Goal: make production-shaped data safe to hand to people who should not see
production. This is usually the reason an organisation adopts synthetic data
in the first place.

- [ ] PII detection with per-field classification: names, emails, phone numbers,
      national identifiers, payment cards, addresses
- [ ] Masking, tokenisation and format-preserving pseudonymisation, with a
      mapping that stays consistent across a run so joins still work
- [ ] k-anonymity and l-diversity measurement on generated output, with
      configurable thresholds that can fail a run
- [ ] Optional differential privacy applied to Phase 9's fitting step, with the
      chosen epsilon stated in the output rather than buried
- [ ] A re-identification risk report suitable for a compliance reviewer
- [ ] Encrypt connection secrets at rest — closes the documented gap where
      `DatabaseConnection` stores its password unencrypted

## Phase 11 — Data Quality and Validation

Goal: prove the generated data is good, instead of eyeballing the first ten rows.

- [ ] Post-run profile of generated output: distributions, null rates,
      uniqueness, correlation matrix
- [ ] Side-by-side real-vs-generated comparison when the project came from a
      Phase 9 profile, with a similarity score
- [ ] Surface what the engine already knows but currently discards: rows
      rejected by rules, unique-pool exhaustion, how much error injection
      actually survived rule filtering (a documented interaction today)
- [ ] User-defined assertions that fail a run — "email must be unique",
      "at least 60% of orders must reach `paid`"
- [ ] An exportable quality report, and the same checks available as a CI gate

## Phase 12 — Connector Expansion

Goal: read from and write to the systems people actually run.

- [ ] Finish MySQL and MongoDB push — both are already modelled in
      `DatabaseDialect` and rejected at runtime, so these are the cheapest
      items on this list
- [ ] Object storage: S3, GCS, Azure Blob
- [ ] Columnar formats: Parquet, Avro, ORC
- [ ] Warehouses: ClickHouse, Snowflake, BigQuery
- [ ] RabbitMQ, and a generic signed-webhook output
- [ ] Matching *input* connectors for Phases 7 and 9, so profiling and schema
      import can read from the same places generation writes to

      Mostly mechanical: the `synthflow.outputs` plugin contract from Phase 5
      already defines how a delivery target plugs in, and the modular-install
      work means each connector's dependencies can ship as its own extra rather
      than bloating the core image.

## Phase 13 — Temporal Continuity and Change Simulation

Goal: records that persist across runs and change over time, instead of every
generation call producing a fresh unrelated universe.

- [ ] Persistent record identity — a customer generated yesterday still exists
      today and can receive new orders
- [ ] Workflow and trend state that carries across calls, closing two documented
      resets: a workflow's walk restarting every call, and a trend's position
      returning to 0 on every batch
- [ ] Simulated inserts, updates and deletes over time (change-data-capture
      shaped), so ETL pipelines and CDC consumers have something realistic to
      chew on
- [ ] Slowly-changing-dimension patterns (type 1 and 2)
- [ ] Backfill a historical window, then continue generating live from its end
- [ ] True `many_to_many` with a real join table — closes the documented
      simplification where it currently generates like `one_to_many`

      The deepest change on this list: it revisits the generation engine's
      assumption that each call is independent, which nearly every Phase 4
      feature was built on top of. Worth attempting only after Phase 8's job
      model exists to run the long backfills it implies.

## Phase 14 — Teams and Governance

Goal: more than one person, and more than one machine, using it safely.

- [ ] API keys / service tokens — today the only authentication is a
      user-password login producing a short-lived JWT, so there is no supported
      way to call SynthFlow from CI at all. Smallest item here, and the most
      immediately blocking
- [ ] Organisations and shared projects, with roles and per-project permissions
- [ ] An audit log of who changed a schema, ran a generation, or pushed to a
      database
- [ ] SSO via OIDC/SAML
- [ ] Project version history with diff and rollback, building on the
      `ProjectTemplate` format that already serialises a whole project design

## Phase 15 — Developer Experience

Goal: use SynthFlow without opening the UI.

- [ ] Python and TypeScript client libraries generated from the OpenAPI schema
- [ ] A full CLI beyond `init` — generate, export, import, run and watch a job,
      tail a stream
- [ ] pytest fixtures and factory-style helpers so a test suite can seed itself
      from a SynthFlow project
- [ ] A GitHub Action, plus recipes for other CI systems
- [ ] A Terraform provider, so a project definition can live in infrastructure
      code alongside the environment it seeds

## Phase 16 — Deployment and Operations

Goal: run it somewhere real, not just docker compose on a laptop.

- [ ] Helm chart and Kubernetes manifests, consistent with Phase 8's worker model
- [ ] A production compose profile: TLS, real secret handling, non-root
      containers, healthchecks, resource limits — today's compose file is
      explicitly a development setup
- [ ] Backup and restore for the control-plane database
- [ ] Documented upgrade path and a version support policy, now that migrations
      and a template format both need compatibility guarantees
- [ ] Optional hosted/multi-tenant mode, with per-tenant isolation and quotas

---

## Future / not yet scheduled

Ideas worth tracking but not committed to a phase yet. Several former entries
here graduated into Phases 7–16 above; what's left is genuinely unscheduled.

- Public plugin/template marketplace — hosted and browsable, rather than the
  file-based import/export that shipped in Phase 5
- A visual React Flow canvas for the relationship and workflow builders; both
  are functional forms today, deliberately
- Synthetic *unstructured* data — documents, images, audio — which is a
  different engine, not an extension of the row generator
- Load/soak profiles: drive a target system at a defined shape of traffic and
  report where it breaks, rather than just emitting rows
