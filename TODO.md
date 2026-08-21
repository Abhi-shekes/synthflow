# TODO

Active task list. This is the working checklist — for the phased overview see
[ROADMAP.md](ROADMAP.md). Keep this file short: only what's in flight or next up.

## Repo bootstrap (not blocking, pick up anytime)

- [x] Initialize repo, README, ROADMAP, LICENSE
- [ ] Add `.github/ISSUE_TEMPLATE` (bug report, feature request)
- [ ] Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Set up CI: lint + typecheck on push (GitHub Actions)
- [ ] Add branch protection on `main` once CI exists

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

## Now

Modular install (`synthflow init` wizard + Web UI service picker) is the
last unstarted Phase 5 item and is still unscoped — it needs its own
design pass. AI provider plugins wait for Phase 6.

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
- When verifying Select/dropdown UI by browser automation, screenshot the
  *closed* control after selecting, not just the open dropdown or the
  eventual result — that's the gap that let the UUID-label bug ship.
- When a route bypasses normal `Depends(...)` dependency injection (the
  websocket stream loop has to, for a fresh short-lived session per tick),
  it also bypasses the test suite's override mechanism unless it looks the
  factory up dynamically (`module.attr`, not `from module import attr`).
  Check this specifically for any future code that touches the DB outside a
  request-scoped dependency.
