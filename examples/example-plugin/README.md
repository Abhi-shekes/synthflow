# Example SynthFlow plugin

A minimal, working example of all three kinds of SynthFlow plugin —
copy this directory as a starting point for your own.

## What it does

- Registers one new preset, `license_plate`, that a STRING field can use
  instead of `faker.word()` or a built-in preset like `pan`/`vin`.
- Registers one new rule function, `is_business_day`, callable by name
  from inside a rule condition, an event-trigger condition, or a formula
  field — the same way the built-in `noise()`/`uniform()` already are.
- Registers one new output plugin, `write_jsonl`, that appends every
  generated batch to a local file as JSON lines — the plugin equivalent
  of `KafkaOutput`/`MQTTOutput`, minus needing a real broker.

## How it works

SynthFlow's backend discovers all three kinds of plugin via Python's
standard
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
mechanism — the same approach pytest, Flask, and many other tools use for
plugins. Any package installed into the same environment as the backend
that declares an entry under one of SynthFlow's entry-point groups is
picked up automatically:

```toml
[project.entry-points."synthflow.generators"]
license_plate = "synthflow_example_plugin.generators:license_plate"

[project.entry-points."synthflow.rule_functions"]
is_business_day = "synthflow_example_plugin.rule_functions:is_business_day"

[project.entry-points."synthflow.outputs"]
write_jsonl = "synthflow_example_plugin.output_plugins:write_jsonl"
```

The right-hand side is `module.path:function_name`.

- A **generator** function must take no arguments and return a
  JSON-serializable value (`str`, `int`, `float`, `bool`, `list`, or
  `dict`) — see `generators.py`.
- A **rule function** can take any number of positional arguments
  (whatever the expression calling it passes) and return whatever the
  evaluator can use — a `bool` for a rule/event-trigger condition, a
  number for a formula — see `rule_functions.py`.
- An **output** function takes `(config: dict, rows: list[dict])` — one
  batch of freshly generated rows, plus whatever free-form JSON config
  the PluginOutput was created with — and delivers them however it
  wants. It can be sync (like `write_jsonl`) or async; SynthFlow runs a
  sync one in a thread so it can't block the event loop. It only owns
  delivery — SynthFlow's generic background loop owns pacing
  (`events_per_second`) and batch loading — see `output_plugins.py`.

## Trying it

From the SynthFlow backend's own environment (wherever `app/main.py`
runs):

```bash
pip install -e /path/to/examples/example-plugin
```

Restart the backend process so it re-discovers installed entry points,
then:

- `GET /api/v1/generator-plugins` now includes `license_plate` with
  `"category": "plugin"`. Create a STRING field with
  `"preset": "license_plate"` — generated rows will contain values like
  `"AB12 CDE"`.
- `GET /api/v1/rule-functions` now includes `is_business_day` with
  `"source": "plugin:synthflow-example-plugin"`. A rule condition like
  `is_business_day(order_date)` or a formula referencing it now works.
- `GET /api/v1/output-plugins` now includes `write_jsonl`. Create a
  PluginOutput with `"plugin_name": "write_jsonl"` and
  `"config": {"path": "/tmp/out.jsonl"}` — that file starts filling up
  with one JSON line per generated row.

To remove it: `pip uninstall synthflow-example-plugin` and restart the
backend again.

## Notes for a real plugin

- A plugin's name can't shadow a built-in name (`pan`, `vin`,
  `nginx_access_log`, `noise`, `uniform`, etc.) — a colliding name is
  skipped, with a warning logged, so a plugin can never silently
  redefine what a built-in means. Output plugins have no built-ins to
  collide with — Kafka/MQTT/REST/WebSocket/Database outputs are separate
  first-party models, not part of this registry.
- A plugin is arbitrary Python code that runs with the same privileges
  as the backend process — there's no sandboxing. Only install plugins
  you trust, the same as any other Python dependency.
- See `app/services/plugins.py` in the main repo for the discovery code
  itself, `app/services/expressions.py` for how a rule function gets
  called from inside an expression, and
  `app/services/plugin_output_producers.py` for the generic
  background-task loop an output plugin runs inside.
