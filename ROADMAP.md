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

- [x] Formal plugin framework — generator plugins only for now; output, rule,
      and AI provider plugins are still just `[ ]` items below, deliberately
      not started in this pass. Real third-party extensibility via Python's
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
