# TODO

Active task list. This is the working checklist — for the phased overview see
[ROADMAP.md](ROADMAP.md). Keep this file short: only what's in flight or next up.

## Repo bootstrap

- [x] Initialize repo, README, ROADMAP, LICENSE
- [x] Add `.github/ISSUE_TEMPLATE` (bug report, feature request)
- [x] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [x] Set up CI: lint + typecheck on push (GitHub Actions) — three jobs.
      Backend runs as a **matrix over both halves of the modular install**
      (core-only and `[all]`), because testing one leg would let the other
      silently break: core proves the app imports and the broker tests skip
      themselves, `all` proves those tests actually run. Frontend runs lint
      and build. A third job validates the compose file, asserts the default
      profile still starts exactly the core three services, and builds the
      backend image both with and without extras. Every job was replicated
      locally before committing — including a clean non-editable install into
      a throwaway 3.12 venv, which is what CI actually does and is not what
      local development does.
- [ ] Add branch protection on `main` — **needs repo-admin action in the
      GitHub UI**; it can't be committed. Suggested: require the `Backend`,
      `Frontend` and `Docker build` checks, and require a PR before merging.

## Phase 1 & 2 — done

Core platform (auth, projects, entities/fields, generation engine) and
simulation (relationships, rules, formulas, stateful entities/workflows) are
both live, backend and frontend, verified end-to-end in a browser. Full
checklists: ROADMAP.md Phases 1–2. Known simplifications carried forward —
`many_to_many` generates like `one_to_many`, workflows are a bounded
per-call random walk with no cross-call record identity yet. (Rules/
formulas gained cross-entity references later — see below — and
event-style triggers shipped in Phase 4.)

## Phase 3 — done (file outputs, database connectors, REST output, plugin
manager, WebSocket streaming)

Full checklist: ROADMAP.md Phase 3. Highlights:

- Excel + project-level CSV zip; `DatabaseConnection` (PostgreSQL v1, MySQL
  modeled but rejected until that driver lands), writing through SQLAlchemy
  Core with parameterized inserts — never string-formatted SQL.
- `RestOutput` and `WebSocketStream`: both public, unauthenticated,
  token-gated (same trust model as a webhook URL) — pull vs. push versions
  of the same idea. The plugin manager is a read-only aggregate
  (`GET /projects/{id}/outputs`) over these typed tables, not a new
  polymorphic model.
- WebSocket streaming is connection-scoped: the production loop *is* the
  WebSocket handler's loop, no persisted "running" state. Kafka/MQTT (not
  started) won't have a client connection to hang that off of and will need
  a real background-task execution model instead.
- Two real bugs found and fixed *while verifying*, not by inspection: Base
  UI's `Select.Value` showing raw ids instead of labels, and a websocket
  route that bypassed the test suite's DB session override by importing
  `SessionLocal` directly instead of looking it up on the module each call.

## Phase 4 — done (all 12 parts)

probability, trend, correlation, error injection, lookup tables, event
triggers, log & security-event presets, API-behavior simulation, timeline
replay, user-behavior simulation, geographic simulation. Full detail lives
in ROADMAP.md Phase 4; the shape worth remembering: four parts (correlation,
API-behavior, user-behavior, and part of lookup tables) turned out to
already be ~90% covered by existing engines and only needed a small real
gap closed, not a new concept — always check existing infra before adding
a model/table. Geographic simulation was the one exception worth flagging:
it genuinely needed new machinery (`GeoRoute`, 2D interpolation across
batch position), confirming the design-pass-first check works both ways —
sometimes it finds nothing to build, sometimes it confirms there really is
something to build. It still reused what it could: waypoints are just
another `LookupTable` upload, a third consumption mode alongside
`LookupAttachment` (sample) and `TimelineReplay` (walk against a clock).

98 new tests across all twelve parts, 154 passed / 3 skipped total, lint
clean. Every part verified end-to-end in a browser, not just by test
suite — most recently: an 11-row generate over a 2-waypoint route produced
an exact linear interpolation (endpoints and midpoint matched precisely),
zero console errors.

## Generated-field and auto-increment field support — done

Turned out to already be fully covered — "generated field" is the
existing `formula` field + `FieldType.UUID`; "auto-increment" is a
`Trend(trend_type=linear, start=1, slope=1)` on an INTEGER field, already
exactly a sequential counter, collision-free by construction so it composes
fine with `unique=True`. No backend code changed. The one real gap was
discoverability: closed with a one-click "Use as auto-increment" preset
button in the trend dialog. 1 new test (50 rows → exactly `1..50`, all
distinct), 155 passed / 3 skipped total. Verified end-to-end in a browser.

## Cross-entity rules + correlation — done

A formula, rule, or event trigger can now reference `RelatedEntity.field`
for an entity connected by a `Relationship` (e.g. an Order's `discount`
formula reading `Customer.discount_rate`) — resolves to the *specific*
linked row, not a random one of that entity. Reused the existing
evaluator (`ast.Attribute`, one level deep, only on names already
resolving to a plain dict — no real attribute/object access) rather than
adding a second mechanism. The real work was generator-side: relationship
-sourced FK fields are now resolved in a pre-pass before an entity's main
field loop, so a formula can see `Customer.age` regardless of whether its
own `order` comes before or after the FK field's. Deliberately project-wide
only — a single-entity `generate` call fails cleanly with "Unknown
variable" since it has no other entity's rows to draw from, the same
asymmetry `Relationship` itself already has (unlike `LookupAttachment`/
`GeoRoute`, which don't need it). 5 new tests including one proving the
formula picks up the *exact* fk-linked customer's rate across 30 orders,
not just any customer's, 160 passed / 3 skipped total, lint clean. Verified
end-to-end in a browser: 10/10 generated orders came back with
`discount = price × Customer.discount_rate` exactly, zero console errors.

## Kafka/MQTT streaming outputs — done

`KafkaOutput` and `MQTTOutput`: entity-scoped, one JSON message per
generated row, into a real broker topic. Introduced the background-task
execution model Phase 3 flagged as missing for this — an in-process
`asyncio.Task` per output (`app/services/stream_producers.py`, module-level
registry), started/cancelled from the app's only two `async def` routes
(create/delete). Bounded retry with backoff (5 failures max, 5s backoff,
5s connect timeout) so a dead broker never hangs a request. Same honest
scope limits as WebSocketStream: no persisted "running" state, no
resume-on-restart, single-process only — documented, not hidden. FastAPI
`lifespan` cancels every live task on shutdown. New `redpanda`/`mosquitto`
docker-compose services, both gated behind Compose profiles so default
`docker compose up` is unaffected. 8 new tests (CRUD only — every test
deletes what it creates to cancel the background task promptly), 168
passed / 3 skipped total, lint clean. Verified against real brokers, not
mocks: produced through the actual UI, consumed 5 real messages off Kafka
with a throwaway `aiokafka` consumer container and 5 real messages off
MQTT with `mosquitto_sub`; separately proved `DELETE` actually stops
production (Kafka topic end-offset unchanged 6 seconds after delete, not
just the DB row gone).

## Generator plugin examples (PAN, VIN, IMEI, GST, QR, email) — done

The first Phase 5 item picked up, ahead of the formal plugin framework it
was listed under — a design pass showed it didn't need that framework to
exist first. `IdentifierPreset` reuses the exact mechanism `LogPreset`
established (a canned generator behind a STRING field's `preset` column):
`pan`, `vin`, `imei`, `gstin`, `qr_code`, `business_email`, in a new
`app/services/identifier_generators.py` mirroring `log_generators.py`.
VIN excludes I/O/Q, IMEI carries a real Luhn check digit; GSTIN's checksum
character is left random rather than guessed at, since that algorithm
isn't public/simple like Luhn's — documented, not hidden. `qr_code` is the
one preset that doesn't fit a plain string well: it renders a real PNG
(new `qrcode[pil]` dependency) encoding a synthetic URL, as a base64 data
URI, which meant teaching `db_output.py`'s Postgres-push column mapping to
use `Text()` instead of `String(255)` for that one preset specifically.
No new model, schema migration, or route — same "check existing infra
first" result Phase 4 kept finding. 9 new tests, 176 passed / 3 skipped
total, lint clean. Verified end-to-end in a browser: a VIN-preset field
generated 10 real 17-character, I/O/Q-free values, zero console errors.

## Formal plugin framework (generator plugins) — done

Real third-party extensibility, not just an internal abstraction: any
Python package installed into the backend's own environment that
declares a zero-arg callable under the `synthflow.generators` entry-point
group (the standard mechanism pytest/Flask/etc. use for plugins) is
discovered automatically and offered as a `preset` — no SynthFlow code
change. `app/services/plugins.py` is the registry; `preset` moved from a
closed `LogPreset | IdentifierPreset` Pydantic union to a plain `str`,
validated dynamically instead of at compile time, since that's the whole
point. A colliding plugin name is skipped (logged, not silently
overriding a built-in); a plugin that fails to load doesn't take down the
others. Deliberately scoped to generators only — output, rule, and AI
provider plugins from the original roadmap line are still `[ ]`, not
started.

`examples/example-generator-plugin/` is a real, working, documented
example package (a `license_plate` generator) — both the "documented
interface" deliverable and this feature's proof: built and
`pip install -e`'d into the actual running Docker backend against
Postgres, not mocked. `GET /generator-plugins` is new; the frontend
preset picker fetches from it instead of hardcoding preset names (the old
`LOG_PRESETS`/`IDENTIFIER_PRESETS` arrays are gone — dead code once
nothing read them), so a newly installed plugin shows up in the UI
without a frontend rebuild.

11 new tests, 187 passed / 3 skipped total, lint clean. Verified live: the
example plugin's preset appeared via the API after a container restart,
generated real rows through the actual UI with zero console errors, and
uninstalling it made both the registry and generation for an
already-created field fail cleanly (400, not 500) rather than silently.

## Template marketplace format — done

`ProjectTemplate`: a project's design — entities, fields, relationships,
rules, event triggers, workflows, trends, error injections, lookup
tables (with their data) and attachments, geo routes — exported as one
JSON document with every reference rewritten from a database id to a
name, and imported back by resolving those names against whatever was
just created in *that* import. Outputs and generated data are
deliberately excluded — outputs hold deployment-specific secrets that
mean nothing to an importer. Import is all-or-nothing: nothing commits
until every reference resolves, so a bad template leaves no partial
project behind. `GET /projects/{id}/export` + `POST /projects/import`;
"Export" button on the project page, "Import project" file picker on the
projects list. This is what makes the "starter templates" item below
buildable next — a starter template is just a curated JSON file in this
shape, no new format work needed.

8 new tests (including a full round trip through every attachment type,
verified by actually generating rows from the *imported* project — not
just comparing JSON shapes), 195 passed / 3 skipped total, lint clean.
Verified end-to-end in a browser against live Docker/Postgres: exported a
real project to a downloaded file, re-imported it through the UI file
picker, zero console errors; separately verified the relational case
(relationship + rule) via the live API, generating 10 real rows from an
imported project that still respected the original's constraints.

## Starter templates (all 11 roadmap domains) — done

banking, stock market, smart city, weather, hospital, manufacturing,
CCTV, logistics, GPS fleet, retail, IoT — each a plain `ProjectTemplate`
JSON file bundled at `app/starter_templates/*.json`, served via
`GET /starter-templates` (list) and `GET /starter-templates/{key}` (the
full template), imported through the exact same `POST /projects/import`
path real export/import already uses. No new model or import mechanism
needed — that's the payoff from making the template format name-based
and hand-editable last round.

Building these surfaced a real gap in that import path first: it was
resolving name references but skipping the type/shape validation each
dedicated create-route already enforces (trend on the wrong field type,
an error type invalid for its field type, a workflow transition to an
unmodeled state, mismatched enum_weights, unknown/conflicting presets).
Fixed by pulling the shared field checks into a new
`app.services.field_validation` (now used by both the normal
add_field/update_field routes and template import) and adding equivalent
checks for trends/workflows/error-injections/lookup-attachments/geo-routes
to the import path — a broken template now fails at import time with a
clean 400 instead of generating silently-wrong data later.

Each template deliberately uses a different slice of the simulation
surface — presets (pan/vin/imei/business_email), auto-increment trends,
a random-walk stock price, seasonal curves, weighted enums, regex
identifiers, branching workflow funnels with `stop_probabilities`,
lookup attachments, geo-routes — so between them they touch nearly
everything Phase 4 built. Frontend: a "Starter templates" gallery on the
projects list, one card per template, "Use template" fetches + imports
in one click; `ProjectTemplate` gained an optional `description` used by
the cards.

26 new tests total (validation-gap fix + the templates themselves,
including one that imports and generates from every bundled template),
212 passed / 3 skipped, lint clean. Verified end-to-end in a browser:
all 11 cards render, "Use template" created a real project through the
UI, and generating from the GPS Fleet template's `LocationPing` entity
produced real interpolated lat/lon points along its bundled route — the
geo-route attachment survived the import intact — zero console errors.

## Rule-function plugins — done

The second half of the plugin framework — not a new `Rule` concept, a new
capability in the expression evaluator every rule/event-trigger
condition and formula already runs through
(`app.services.expressions.evaluate`). A package installed into the
backend's environment that declares a callable under the
`synthflow.rule_functions` entry-point group becomes callable *by name*
from inside any expression, the same way built-in `noise()`/`uniform()`
already are. Discovery lives next to the generator-plugin mechanism in
`app/services/plugins.py`, sharing `PLUGIN_API_VERSION` and the same
collision/broken-plugin handling, but stays one-directional
(expressions.py imports plugins.py, not the reverse) — `GET
/rule-functions` merges built-ins and plugins at the route layer instead
of inside plugins.py, to avoid a circular import.

Writing the example plugin (`is_business_day`, added to
`examples/example-plugin/` — renamed from `example-generator-plugin`
since it now covers both plugin kinds) surfaced a real bug: a rule's
condition is validated against dummy stand-in values at creation time,
and every field's stand-in was hardcoded to the integer `1` regardless
of its real type, so a date-specific function on a DATE field raised an
unhandled `TypeError` that surfaced as a raw 500. Fixed two ways —
`dummy_row_values` now picks a type-appropriate stand-in per field type,
and `evaluate()`'s function-call handling now wraps any exception a
called function raises in a clean `ExpressionError` regardless of cause,
so a condition can never 500 the server no matter what a plugin does
internally.

15 new tests (13 for the plugin mechanism, 2 regression tests for the
bugs found), 227 passed / 3 skipped, lint clean. Verified against the
real installed example plugin: the exact rule that 500'd before the fix
created cleanly after it, and generating rows against Postgres confirmed
every single generated date actually landed on a weekday — the rule was
genuinely calling the plugin function per candidate row through the
discard-and-regenerate loop, not just accepting the condition
syntactically. Confirmed in a browser too, and confirmed uninstalling
the plugin degrades cleanly (disappears from the list, a new rule
referencing it gets a 400).

## Output plugins — done

The third and final piece of the plugin framework — AI provider plugins
are the only category left, and those wait for Phase 6. Unlike Kafka/
MQTT, an output plugin's config shape isn't known until it's installed,
so there's one generic `PluginOutput` model (`plugin_name` + free-form
JSON `config`) instead of a new typed table per plugin. Any package
declaring a callable under the `synthflow.outputs` entry-point group
becomes a selectable `plugin_name`, receiving `(config, rows)` once per
tick; a new generic background loop
(`app/services/plugin_output_producers.py`, a sibling to
`stream_producers.py`, not a refactor of it — Kafka/MQTT's working code
stayed untouched) owns pacing and batch loading, the same
asyncio.Task-per-output model as Kafka/MQTT. Delivery can be sync or
async — a sync one just runs in a thread.

`examples/example-plugin/` grew a third entry point, `write_jsonl`,
deliberately network-free (appends batches to a local file) so live
verification didn't need a broker. `GET /output-plugins` lists installed
ones; the entity page's new "Plugin output" card picks from that list
and takes config as raw JSON.

8 new tests, including one that goes past CRUD: a fake in-memory plugin
records every batch it receives, and the test waits on the *real*
background asyncio.Task to actually call it with real generated rows —
possible here (unlike Kafka/MQTT's tests) because a plugin output's
"broker" is just a Python function, not an external service. 235 passed
/ 3 skipped total, lint clean. Verified against the real installed
plugin: a real file inside the backend container filled up with real
generated rows against Postgres; separately proved DELETE genuinely
stops the producer the same way as Kafka/MQTT (line count unchanged 4s
after delete). Confirmed in a browser too, and confirmed uninstalling
degrades cleanly (disappears from the list, a new output referencing it
gets a 400).

## Live monitoring dashboard — done

All six things the roadmap listed (events/sec, active streams,
CPU/memory, connected clients, errors, output status), as a *provisioned*
Grafana dashboard rather than just an exposed `/metrics`:
`docker compose --profile monitoring up` and it's there at :3001, both
datasources wired, no setup step. Four new profile-gated compose services
(prometheus/grafana/loki/promtail, configs in `monitoring/`), so the
default `docker compose up` is unchanged.

The design-pass win: the "active" gauges **read existing state instead of
counting it**. Both producer modules already keep a module-level `_tasks`
registry of live tasks — that registry already *is* the count — so those
gauges are `set_function` callbacks over `len()`, with zero
instrumentation added to the producers and no second source of truth to
drift. Connected WebSocket clients is the only real inc/dec gauge (no
registry exists there), with `dec()` in a `finally` because that loop also
exits via two early returns and cancellation.

Second decision worth remembering: every label value comes from a fixed
hardcoded set, never a project/entity/field name. That's what makes
serving `/metrics` unauthenticated defensible (Prometheus can't refresh a
JWT), and there's a test asserting distinctive user-supplied names never
appear in the scrape body — so a future entity-labelled metric fails
loudly rather than quietly leaking schema names. Row counting/timing does
need call-site instrumentation, but it went at the 8 boundaries that know
their own identity (via a `metrics.generation(source)` context manager)
rather than as a new argument threaded through `generate_rows` — so
`generator.py` has no metrics code in it at all.

13 new tests, 248 passed / 3 skipped, lint clean. Verified live against
the full 7-container stack: counter moved by exactly the number of rows
generated, Prometheus scraped it and `rate()` was non-zero, Grafana
proxy-queried Prometheus with all 12 panels provisioned, Loki had real
backend logs. Then the live gauges were driven for real — a real
WebSocket client took the client gauge 0→1→0, and a Kafka output aimed at
an unreachable broker took `active_producers{kafka}` 0→1, logged 3
delivery errors through the backoff path, and returned to 0 on delete.
Dashboard screenshotted under load and inspected: every panel populated,
no "No data", no console errors.

## Modular installation — done (completes Phase 5)

Genuine, not cosmetic. `aiokafka`/`aiomqtt` were *core* deps until now,
so every install pulled both — the opposite of modular. They're optional
extras now, which forced three real changes: `stream_producers` imports
its broker client inside the loop that needs it (so the module imports
on an install with neither); `app/services/install.py` detects
availability with `find_spec`, not a real import, since it's called per
request; and the create routes 400 with a message *naming the extra to
install* instead of 500-ing or spawning a task that dies on tick one.

`synthflow init` (`app/cli.py`, a real console script) writes one `.env`
with `COMPOSE_PROFILES` (which services start) and `SYNTHFLOW_EXTRAS`
(which extras the image installs, via a Docker build arg). It
deliberately does NOT generate a compose file — Compose already reads
COMPOSE_PROFILES and the profiles already exist, so a generated file
would just be a second source of truth that drifts. Interactive by
default, non-interactive for CI, rewrites only its own two keys so it
can't eat a SECRET_KEY, and walks up to find the repo root.

The Web UI half is honest about the browser's limits: it can't restart
Docker (and shouldn't have the socket), so `GET /install-config` reports
what's actually installed and the entity page greys out Kafka/MQTT when
their extra is missing, naming the command that enables it.

19 new tests; the 4 broker-output tests are now skipif-gated on their
extra, which is the feature working. Verified both directions: extras
removed → app imports, reports both False, 263 passed / 7 skipped;
`.[all]` installed → 267 passed / 3 skipped. Build arg verified by
building two real images — core-only has neither client, a
`SYNTHFLOW_EXTRAS=kafka` image has aiokafka and genuinely no aiomqtt
while still booting. Wizard verified end to end: `--services
kafka,monitoring` produced an .env that made compose resolve to core +
redpanda + 4 monitoring services and no mosquitto. An idempotency test
caught a real bug (the banner comment stacking on every re-run), fixed.

## Phase 7 — Schema Import — done

Four importers (live database, SQL DDL, JSON Schema/OpenAPI, sample data
file), all sharing one shape: **an importer returns a `ProjectTemplate`
and creates nothing.** Applying it is a separate `POST /projects/import`
call. That makes the mandatory review step structural rather than a UI
convention — there's no code path from "read a database" to "rows in the
database" — and reuses Phase 5's proven all-or-nothing apply instead of a
second creation path that could drift. A test asserts an import leaves
the project count unchanged.

The other half of every result is `warnings`. Every importer is lossy
(no check constraints, composite keys, or TIME type in SynthFlow), and
silently dropping those is the worst outcome — the project looks complete
while meaning something different from its source. So each is named.

Notes worth keeping:
- SQL parsing uses `sqlglot`, not regexes. Probing it against realistic
  DDL immediately caught two bugs in my first pass: `NOT NULL` handling
  was inverted (sqlglot models `NOT NULL` and explicit `NULL` with the
  same node, distinguished by an `allow_null` arg), and inline
  `REFERENCES` produced no relationship because only table-level
  `FOREIGN KEY` was handled. Both are common in real dumps.
- Verifying against a real Postgres schema — rather than a fixture —
  surfaced a genuine quality gap: `SERIAL` keys generated random
  seven-digit integers. SynthFlow already expresses auto-increment as a
  linear trend (Phase 2), so importers now attach one.
- Parquet moved to Phase 12, where columnar formats already live and
  `pyarrow` can be an optional extra rather than core image weight.

42 new tests, 309 passed / 3 skipped, lint clean. Verified against a
deliberately awkward live schema (quoted column with a space, CHECK
constraint, composite primary key, TIME/TIMESTAMPTZ/JSONB/UUID/SMALLINT,
two foreign keys): everything imported, both FKs became relationships,
all four lossy conversions reported, and generating from the applied
project produced genuinely referential rows. Browser-verified end to end
with zero console errors.

## Phase 8 — Scale and Scheduled Jobs — done

Streaming generation, a persistent job queue, cron schedules, and the end
of "background work doesn't survive a restart".

**The architecture call:** the job table *is* the queue, claimed with
Postgres `SELECT ... FOR UPDATE SKIP LOCKED`. The tech-stack table said
Celery + Redis; this uses the database instead, deliberately. Three
things then fall out rather than needing infrastructure — jobs survive a
restart by construction (they're rows), exactly one worker runs a given
job, and there's no Redis or worker container to deploy. Celery would
have added two containers and a second deployment shape for what
Postgres already does well at this scale. README's table now says so.

Notes worth keeping:
- `generate_rows` became a thin wrapper over a new `iter_rows` generator.
  The accumulated list was used for exactly one thing (the previous row),
  which is why the refactor was small. 50k rows: 25 KiB streaming vs
  11 MiB as a list.
- A scheduled run is *just a job* — the worker inserts an ordinary queued
  row. One execution path, and scheduled runs get the same history,
  progress and artifacts.
- The cron parser is ~80 lines rather than a dependency, and refuses
  `0 0 31 2 *` at creation: a schedule that silently never fires is worse
  than one that won't be created.
- Two bugs surfaced only against real Postgres, not the SQLite suite:
  boolean columns declared `Integer` (Postgres rejects `IS TRUE` on an
  int), and `resume_producers` calling `asyncio.create_task` inside
  `asyncio.to_thread` where there's no running loop. A third — a
  schedule rendering "Invalid Date" — was caught by looking at the
  screenshot rather than the assertions.
- Backpressure/rate limiting is the one item left open, not faked:
  producers already pace by `events_per_second`, so the real work is
  reacting to a slow consumer, and that wants Phase 11's quality signals
  to define "too slow".

37 new tests, 346 passed / 3 skipped, lint and format clean. Verified
live: a 250,000-row job (50x the interactive cap) in 9.6s with progress
observable throughout, 4 MiB artifact of exactly 250,001 lines whose
weighted enum held at 80/15/5, backend RSS steady at 123 MiB;
cancellation stopped a 3M-row job at 24,000 rows; a once-a-minute
schedule fired on its own; SKIP LOCKED gave 40 unique claims across 8
concurrent threads with zero doubles; and a real container restart left
the Kafka producer resuming on its own (+44 messages).

## Phase 9 — Learn From Real Data — done

Upload real sample files, get a project whose generated data has the
*shape* of the original rather than just its schema. `POST /profile`
(multi-file), plus a "Sample data file (learn distributions)" option in
the existing import dialog, reusing Phase 7's review-then-apply flow.

- Numeric columns are fitted to normal/lognormal/exponential/uniform by
  decile comparison, and **prefer uniform unless something fits clearly
  better** — a confidently-wrong shape is worse than an honest shrug.
  Every fit reports `close`/`approximate`/`rough`.
- Correlations become fitted formulas with residual noise
  (`total = 0.26 + 19.98 * qty + noise(3.93)`), only ever pointing
  backwards through column order so they can't cycle.
- Cross-file relationships are detected, which is the whole reason the
  endpoint takes several files at once.

**No new models, no migration** — the win of this phase, and it came
straight from the "Notes for future me" entry below. Categorical
frequencies were already `enum_weights`, correlation was already the
formula engine, and distributions became four functions in
`expressions.py` (`gauss`, `lognormal`, `expo`, `triangular`). Only the
profiler itself was new. Stdlib `statistics` throughout — no numpy/scipy.

Three bugs found only by profiling real multi-file data, all now with
regression tests: value containment alone linked `orders.qty` (1–13) to
`customers.cid` (1–900) because small ints are always "contained" in a
big id column; a 13-distinct quantity column was bucketed as categorical,
silently dropping it from correlation detection and reducing `total` to a
meaningless `gauss(120, 41)`; and the bogus reciprocal links formed an
entity cycle that imported fine then failed with HTTP 400 on generate.

**Known limit:** fields have a fixed null probability, so an observed
8%-null column won't generate 8% nulls. The profiler measures and reports
the real rate instead of pretending — honouring it needs a per-field
null-rate column, which is a schema change this phase chose not to make.

374 passed / 3 skipped, lint and format clean. Verified live: 900
customers + 2,000 orders recovered `age → round(gauss(44.44, 11.59))`,
`income → lognormal(10.52, 0.56)`, `total → 0.26 + 19.98 * qty +
noise(3.93)` against a true `19.99 * qty + gauss(0, 4)`, with only the
real FK kept. Generated-vs-source: age mean 44.32 → 44.61, `free` 67.6%
→ 66.9%. Browser-verified, zero console errors.

## Phase 10 — Privacy and Compliance — mostly done

Phase 9 opened a real hole and this closes it: profiling a staff file
produced a project containing real names and real email addresses as enum
values, plus two employees' exact salaries as a `uniform()` range. Both
were demonstrated before being fixed, and both have regression tests.

- **PII classification** (`app/services/privacy/classify.py`) on column
  name *and* value patterns. Name evidence alone never reaches `high`,
  and only `high` is redacted automatically — a false positive that
  replaces a column someone cared about is worse than a line in a report.
- **Replacement, not masking**: a classified column is pointed at a
  synthetic generator registered in the existing preset registry, so this
  needed **no new column and no migration** — the third phase in a row to
  reuse that extension point. Redaction sits in `_to_field` ahead of every
  branch that could emit an observed value, so it is structural.
- **Bounds rounded outward** so a fitted range stops naming the exact
  values of the lowest and highest record.
- **k-anonymity / l-diversity** measured on generated rows via
  `POST /projects/{id}/entities/{id}/privacy-report`, reporting k, l, the
  share of rows below threshold, and *which* combinations are rare.
  Measures, never alters — an automatic fix would silently change the
  distribution the user came for.
- **Connection passwords encrypted at rest** (`app/core/secrets.py`),
  Fernet keyed off `SECRET_KEY`, applied as a SQLAlchemy column type so
  no code path can write the column in plaintext.

**Not built, deliberately:** consistent-mapping pseudonymisation (a
reversible pseudonym is still personal data; the cost of the irreversible
choice is that joins *on a name* across two profiled files won't hold —
joins on ids still do), and differential privacy on fitting (only
meaningful with a real sensitivity analysis and budget accounting; an
implementation stating an epsilon it doesn't achieve is worse than none).
Thresholds are per-request on the report endpoint — making them fail a
scheduled *job* needs a per-entity policy column.

**Known limits:** classification is regex and keywords, so it misses
personal data in free text and knows only the identifier formats listed.
Encryption protects against a dump or a stray SELECT, not against an
attacker holding the app environment — they have `SECRET_KEY` and so the
key. Rotating `SECRET_KEY` now invalidates sessions *and* makes stored
secrets undecryptable (loudly, with an explanatory error).

37 new tests, 421 passed / 3 skipped. Verified live: a 400-row patient
file had name/email/phone/dob redacted while `city`, `plan` and
`annual_cost` were learned normally; the migration encrypted three real
plaintext passwords in the running Postgres; the report endpoint gave
k=231 for a coarse quasi-identifier over 1,000 rows and k=1 (68% of rows
below threshold) for a fine one over 60.

## Phase 11 — Data Quality and Validation — mostly done

`POST /projects/{id}/entities/{id}/quality-report`, a browser dialog, and
`synthflow check` as a CI gate — all rendering the same payload, so what a
reviewer reads and what fails a build cannot drift apart.

Three parts, deliberately separate because they carry different authority:

- **diagnostics** — what the engine saw while generating, and the only
  place a *silent* failure shows up. Candidates discarded by rules
  (attributed to the first failing rule, so counts sum rather than
  double-count), unique retries per field, error-injection survival.
  Opt-in, so Phase 8's streaming path stays exactly as cheap.
- **observation** — what the rows contain, via Phase 9's `profile_column`
  rather than a second profiler, plus `violations` where output
  contradicts the field's own declaration. A violation is a defect.
- **assertions** — the user's bar. `email.unique`,
  `status.share_paid >= 0.6`.

**No evaluator changes were needed for assertions**, which is the design
win. The evaluator already resolves one level of attribute access on a
dict in `variables` (the Phase 2 `Customer.age` mechanism), so assertions
just put per-field aggregates under each field's name — inheriting the
sandbox and the installed rule-function plugins for free.

**What it caught immediately:** a rule `amount > 400` on a field declared
`min 1, max 500` discards **79% of candidates** and produces
`uniform(400, 500)`. Nothing errored, the requested rows came back, the
data looked fine — the field config had just stopped describing the
output. Same mechanism surfaces the long-documented error-injection
interaction: corruption runs before rules, so 50% corrupted emails plus a
non-null rule yields **0%**, silently.

**Not built:** real-vs-generated side-by-side with a similarity score. It
needs a decision this phase didn't make — Phase 9 persists nothing about
the source on purpose, so a true comparison needs the original file
re-uploaded or the source profile stored, re-introducing the artefact
Phase 9 avoided. The honest half exists: observed fit sits next to
declared config, so drift is visible without keeping anyone's data.

**Known limits:** diagnostics cover one entity, not a `generate_project`
run. Assertions are per-request, so a scheduled job can't fail on them —
the same per-entity policy column Phase 10's thresholds want, worth adding
once rather than twice. `share_` names are sanitised, so two categories
differing only by punctuation can collide; every available name is
returned so a user can see what they got.

25 new tests, 446 passed / 3 skipped. CLI gate verified live (exit 0 / exit
1); browser dialog verified with zero console errors.

## Phase 12 — Connector Expansion — done, five of six bullets

Input and output are now symmetric: every place a generation job can write
to is a place profiling can read from. MySQL and MongoDB push, S3-compatible
object storage, Parquet/ORC/Avro job formats, RabbitMQ and a signed webhook,
and matching *input* connectors for URLs, buckets and database tables.

**Warehouses (ClickHouse, Snowflake, BigQuery) were skipped at the user's
request** — deliberately, not forgotten. Two of the three need paid cloud
accounts that can't be verified against anything real here, and a connector
nobody has run against its actual service doesn't get ticked off.

### Push connectors (MySQL, MongoDB)

- Both ship as **optional extras** (`pymysql`, `pymongo`) in the same
  `install.FEATURES` registry Kafka and MQTT use, so a core install carries
  neither driver and reports how to add one instead of an ImportError.
  Postgres needs no extra — its driver is already vendored.
- **MongoDB reuses `DatabaseConnection`** rather than getting its own
  model. Credentials, encrypted password, ownership checks and the whole UI
  are identical; only the write path differs. One dispatch beats a
  duplicated model, API and frontend.
- Where they genuinely differ, they differ on purpose: SQL serialises a
  list to a JSON string because a column can't hold one, MongoDB keeps a
  real array. A DATE stays an ISO string rather than becoming a midnight
  BSON timestamp, because BSON has no date-only type and promoting it
  invents a timezone question. Documents are restricted to declared fields
  — schemaless is not a reason to be shapeless.
- Real compose services under `mysql`/`mongo` profiles, on non-default host
  ports (3307, 27117), so trying this doesn't collide with a database you
  already run locally.

**Known limits:** MongoDB authenticates against `admin`, which the official
image and Atlas both expect; a user created *inside* the target database
needs a per-connection auth-source setting, which is a schema change. The
dialect migration is **irreversible** — Postgres has no
`ALTER TYPE ... DROP VALUE`, so `downgrade` is a documented no-op.

Verified against real servers: 50 rows into MySQL 8.4 with correct inferred
column types, 50 documents into MongoDB 7, then the whole path again through
the HTTP API where Phase 10's encrypted password authenticated without ever
appearing in a response.

**Environment note:** MySQL wouldn't start here — `io_setup() EAGAIN`,
because InnoDB grabs kernel AIO contexts at startup and the host's
`fs.aio-max-nr` was exhausted by other containers. The service runs with
`--innodb-use-native-aio=0` rather than asking anyone to retune their
kernel.

### Input connectors — learn from a URL, a bucket or a table

Phases 7 and 9 could only learn from a file uploaded through the browser.
Now the same bucket a job uploads to, and the same database a push writes
into, can be read back as a sample.

- **URLs and objects produce bytes**, so they reuse the upload-parsing path.
  They *are* files; a second CSV parser would be a liability.
- **A database produces rows**, and `profile_table()` / `profile_tables()`
  split out of the file versions so it reaches profiling without a CSV
  round-trip. That's the whole point: a table serialised to CSV and read
  back loses DATE and DATETIME to strings, so the file path would have
  profiled a database **worse** than the same data exported by hand. Read
  from real MySQL, `issued_on` is a `date` and `settled_at` a `datetime`;
  as CSV, both are strings.
- **`DECIMAL` was the bug this found.** SQL money columns arrive as
  `decimal.Decimal` — neither `int` nor `float` — so the profiler classified
  them as *strings*. `ingest._normalise` converts it, narrowly; normalising
  everything unknown would paper over the next type that needs thought.
- **`project_id` is optional, and only for URLs.** Keys and tables need
  credentials that belong to a project; a public URL needs none, and
  demanding one would mean you couldn't learn from a URL until you'd already
  made a project to learn into.
- **Only `http` and `https`.** `urllib` supports `file://` and `ftp://` by
  default, which would turn "profile from a URL" into a way to read the
  server's own disk. Every source is size-bounded before it reaches memory.
- A 404 that lied got fixed on the way: `object_storage._readable()` was
  written for `head_bucket`, so reusing it for `head_object` made a mistyped
  **key** report "Bucket does not exist" about a bucket that was fine.

**The screenshot habit caught two more.** The UI typechecked and still
shipped a select rendering the raw value `object` instead of "Object
storage", and a placeholder telling people to repeat a prefix the backend
already applies. A third came from reading the code: the project-creation
call sat in an `onSuccess` chain where a failure could never reach
`onError`, so a failed import would have shown the user nothing.

**537 passed / 5 skipped** at the close of the phase, lint, format and
typecheck clean. All three input paths driven in a real browser against
MinIO, MySQL and a real HTTP server — including the error path, which now
names what was actually missing.

## Phase 13 — Temporal Continuity and Change Simulation — done, all six bullets

The deepest change on the roadmap: it revisits the generation engine's
assumption that every call is independent, which nearly every Phase 4 feature
was built on top of.

A **`RecordStore`** is a population of one entity's records that survives
between calls. From it everything else follows.

- **Persistent identity.** `generate_new` adds records; `identity_pool` hands a
  child entity the identity values of a parent's *stored* records. Orders
  generated today reference customers generated last week, because the
  customers are still there to reference.
- **`identity_field` is required**, and that constraint is the feature.
  Persistent identity means knowing what makes two rows the same record. A
  hidden surrogate key would have been identity in name only — nothing
  downstream could join on it, so a consumer could not tell an update from an
  unrelated insert.
- **Trends and geo routes finally have a cursor.** `iter_rows` gained
  `start_position` and a mutable `trend_state`; both default to the old
  behaviour, so all six existing call sites are untouched. A linear trend
  continues across the call boundary; a `random_walk` keeps its running value.
  `generate_geo_point` wraps instead of clamping, or every vehicle would have
  frozen on its destination from the second tick.
- **The workflow reset needed identity first.** A fresh walk per *row* is
  correct for a batch — it is what makes a funnel look like a funnel. The reset
  only matters for the *same record seen twice*, so the fix lives on the update
  path: `advance_state` steps one hop from where the record already is.
- **CDC.** A per-store change log read from a cursor, `before`/`after` in
  Debezium's shape. Inserts, then updates, then deletes within a tick: a record
  inserted by this call can be updated by it; one deleted by it cannot. Deletes
  are tombstones, which is also what stops a later insert recycling a dead
  key.
- **SCD type 1 and 2.** Type 1 overwrites (the default, and what the store
  already did). Type 2 versions every change, `valid_to` null exactly on the
  current one — no `is_current` flag that could disagree with it. Types 3, 4
  and 6 deliberately absent.
- **Backfill, then continue live.** Each tick carries its own `event_time`, so
  history spreads across the window rather than collapsing into one instant.
  `created_at` still says now.
- **True `many_to_many`.** A join table, `min_links`..`max_links` distinct
  targets per source row. **Behaviour change:** the type used to generate
  exactly like `one_to_many`; it now means what it says.

**The bug worth remembering.** The suite was green at 33 continuity tests when
the version-history panel showed a first interval running
`2026-08-22 → 2026-08-19`. A record created today has a version starting today,
so a backfilled update dated last week closes it before it opened. Every test
had backfilled into a clean store, so none of them could see it. The first
guard written was subtly wrong — it compared the window against the *earliest*
existing event, which the failing case satisfies — and the honest rule (a
backfill must be a store's first activity) turned out simpler than the clever
one.

**Known limits.** Change events accumulate; the log is bounded by churn rather
than output volume, but trimming stays a manual decision because only the
operator knows whether every consumer has caught up. A backfill cannot extend
an existing history further back.

**576 passed / 5 skipped**, lint and typecheck clean. Verified against real
Postgres and in a browser: a trend running 100 to 195 unbroken across a call
boundary, 30 orders referencing 16 of 20 persisted customers and nothing else,
a gapless change log replayed through a paged cursor, and 38 closed type 2
intervals none of which run backwards.

## Phase 14 — Teams and Governance — done, five bullets (SAML excluded)

The phase's shape was set by one discovery: **"may I touch this project" was
two helper functions behind 118 route call sites.** Everything else went in
behind them without a route changing.

### API keys

- Both credential kinds arrive as a bearer token, so every route, client and
  test keeps working and a pipeline sets the same header a browser does.
- **SHA-256, not bcrypt.** A key is 32 random bytes — nothing to guess, so
  bcrypt's slowness costs every request and buys nothing. A cleartext,
  indexed prefix makes verification one lookup and one constant-time compare.
- Read-only is enforced **by request method**, not an endpoint list. A list
  is a thing you forget to update, and forgetting means a read-only key that
  can write.
- A key cannot manage keys: a leaked one that can mint more outlives its own
  revocation. Revocation is a timestamp, not a deletion.
- **The bug:** `secrets.token_urlsafe` emits `_`, and splitting on every
  underscore broke ~half of all keys. Intermittent, so it read as test-order
  flakiness until 30 real keys showed 22 carrying the character.

### Organisations and roles

- A **ladder, not a matrix**: viewer → member → admin → owner, each
  containing the one below. A permission matrix is more expressive and is
  the thing nobody can reason about.
- `Project.organization_id` is nullable; personal projects are unchanged.
- Owner always outranks the org on their own project. Only the owner
  re-shares it. Unseen project = 404, not 403. An admin cannot grant above
  their own role. The last owner cannot be removed. Dissolving an org
  **returns** its projects rather than deleting them.
- **Two bugs.** A contextvar set inside a sync dependency never reached the
  route handler — FastAPI runs those in a worker thread with its own context
  copy — so every request read as a GET and **a viewer could write**. And
  `ON DELETE SET NULL` is not enforced by SQLite, so org dissolution was
  only correct in production and untested anywhere.

### Audit log

- **Middleware, not calls in routes.** A log assembled by remembering to log
  has invisible holes.
- Mutating methods only. **Refusals kept** — and that was the bug: the actor
  was recorded on the success path, so every 403 arrived with no "who" and
  was dropped. The log silently lost exactly what it existed for.
- `user_id` is SET NULL with the email denormalised; `route` is
  router-relative so a version bump does not split one route's history.

### SSO (OIDC)

- Discovery fetched, state a signed token rather than a row, **nonce
  checked** — the part that stops a replayed id_token and the part most often
  skipped because nothing visibly breaks without it.
- Tokens return in the **fragment**, never the query string, and the frontend
  clears them from the address bar.
- No new dependency: PyJWT is already core, HTTP is stdlib `urllib`.
- **Verified against real Dex**, behind an `sso` compose profile. The stub in
  the suite exists only for what a real IdP will not do on demand.
- **SAML deliberately not implemented** — `xmlsec` is a native build burden
  and there is no IdP here to verify against. Same rule as Phase 12's
  warehouses.

### Version history

- Built on `ProjectTemplate`, so one table rather than a schema that would
  drift from the real one.
- **Explicit snapshots.** Auto-versioning every mutation produces a history
  nobody can read. Rollback always snapshots first — you cannot ask someone
  to have predicted their own mistake.
- **Structural diff**, matched by name. `order` excluded, or inserting a
  field reports a change to every field below it.
- Rollback refuses to destroy populated record stores unless told; an empty
  store does not block it.
- Version numbers come from a counter, not `max + 1` — deleting the newest
  snapshot would otherwise recycle a number somebody referred to last week.

**659 passed / 5 skipped**, lint and typecheck clean. Verified against the
running stack and in a browser: four roles on a shared project, a read-only
key refused by method, SSO through Dex, and a snapshot–diff–rollback round
trip.

## Closed debt — per-field null rates

Phase 9 shipped with a documented limit: every nullable field generated
nulls at a flat 15%, so profiling could *measure* a column's real rate — and
warned that it could not reproduce it — but not honour it. Closed.

`EntityField.null_probability` now carries the rate end to end: profiling
writes what it observed, export/import and version history round-trip it,
and generation uses it.

- **NULL means "unspecified", distinct from an explicit `0.0`.** Unspecified
  takes the engine default, which is exactly what every field meant before
  the column existed — no existing project shifted. `0.0` means never null,
  and is a real thing to ask for that nothing else expresses.
- **A rate on a `required` field is refused, not ignored.** The generator
  would ignore it, but a value stored and silently disregarded is a setting
  somebody will read back, believe, and be wrong about. Checked against the
  field as it *will* be, so making a field required later is refused too.
- The profiler's warning changed rather than vanishing: it now flags a
  column more than 90% empty, because faithfully generating 95% nulls is
  rarely what anyone wanted even though it is now what happens.
- One shared `common` dict in `_to_field` feeds every profiling branch, so
  enum, numeric, redacted and plain-string fields all got it in one edit —
  and a branch added later gets it for free.

**Two fixture bugs of my own, worth remembering.** An empty value in a
single-column CSV is a *blank line*, which the reader skips entirely rather
than reporting as a row with a missing cell — so a one-column fixture
measures 0% nulls however many blanks it has. And all-distinct sample values
make the column profile as `unique`, after which generation cannot mint
enough distinct strings to fill a batch.

**683 passed / 5 skipped**, lint and typecheck clean. Verified against the
real stack: a 500-row sample with columns at 2.2% and 37.8% missing produced
generated columns at 2.4% and 37.5% over 3,000 rows. Both would have been
15% before. Driven in a browser too — the input appears only for a nullable
field, disappears when Required is ticked, and the field list shows
"35% null" only when a rate was actually set.

## Now

**Phases 1–5 and 7–14 are done**, several with deliberate exclusions —
Phase 12's warehouses (skipped at the user's request) and Phase 14's SAML.
Phase 6 (AI) stays deliberately unstarted; nothing depends on it.

Next is **Phase 15 (Developer Experience)**: generated client libraries, a
full CLI beyond `init`, pytest fixtures, a GitHub Action and a Terraform
provider. Phase 14's API keys unblocked all of it — until this release there
was no supported way to call SynthFlow from anything but a browser.

**Worth doing once, not twice:** a per-entity policy column would let both
Phase 10's k-anonymity thresholds and Phase 11's assertions fail a
scheduled Phase 8 job. Two phases have now wanted it.

**Test-database race, fixed but worth remembering:** conftest binds every
session to ONE SQLite in-memory connection (`StaticPool`,
`check_same_thread: False`). Any background producer that opens its own
short-lived session on a worker thread shares that connection, and its
`close()` returns it to the pool — rolling back whatever transaction is on
it. That intermittently undid a committed DELETE, surfacing as a 204
followed by the row still being listed. Production never hits it (Postgres
gives each session its own connection). Tests that exercise CRUD around a
producer now request the `no_background_producer` fixture. Any future
connector with a background loop will have the same hazard.

**A test-writing habit worth keeping:** three tests across Phases 10 and 12
failed purely because they hardcoded a set or count that a new feature
legitimately changed (`{"kafka", "mqtt"}`, `11 + 6` presets). Each said
nothing about whether the mechanism worked. Derive the expectation from the
registry being tested.

The quick win still available anywhere: **API keys** (Phase 14 — there's
still no machine authentication, which blocks CI use). The other item that
sat here, MySQL/MongoDB push, shipped in Phase 12.

## Backlog (not started, roughly in order)

(empty — see Phase 5 above)

## Notes for future me

- Keep everything past the core behind a plugin boundary from day one — retrofitting
  "modular install" onto a monolith later is much more painful than designing for it
  now (see ROADMAP.md Phase 5). Phase 3 outputs are exactly the kind of thing that
  needs to be added/removed per-deployment later.
- AI stays fully optional and out of the critical path until Phase 6 — don't let it
  leak into the core data model or generation engine before then.
- `app/services/expressions.py` is shared infrastructure — reuse it for anything
  else that needs a user-authored expression (event triggers, cross-entity
  rules/correlation) rather than writing a second evaluator. Before building a new
  "engine" as its own model/table, check whether it's actually just a formula or
  rule with a missing capability (like `noise()`/`uniform()` turned out to be for
  correlation) — cheaper to extend the evaluator than to add a new concept.
  Phase 9 is the strongest evidence so far: following this note is what let an
  entire phase ship with zero new models and zero migrations.
- A heuristic that decides to *change* the user's data needs probing against
  realistic inputs before it ships, and separate confidence levels so only the
  strong evidence acts. Every Phase 10 classifier bug was a false positive —
  income read as phone numbers, company names read as people — and each would
  have silently replaced a column the user cared about. The generic version:
  when a check can fire wrongly, make the cheap outcome (a report line) the
  default and reserve the destructive one for unambiguous evidence.
- Anything that infers structure *across* inputs (Phase 9's relationship
  detection, and Phase 12's schema diffing when it arrives) needs testing on
  real multi-file data, not fixtures. All three Phase 9 bugs needed the
  *combination* of two real files to appear, and every one of them passed the
  unit suite. Heuristics that look obviously right on one table — "these values
  are all contained in that column, so it's a foreign key" — are routinely
  wrong on two.
- When verifying Select/dropdown UI by browser automation, screenshot the
  *closed* control after selecting, not just the open dropdown or the
  eventual result — that's the gap that let the UUID-label bug ship.
- When a route bypasses normal `Depends(...)` dependency injection (the
  websocket stream loop has to, for a fresh short-lived session per tick),
  it also bypasses the test suite's override mechanism unless it looks the
  factory up dynamically (`module.attr`, not `from module import attr`).
  Check this specifically for any future code that touches the DB outside a
  request-scoped dependency.
