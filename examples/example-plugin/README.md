# Example SynthFlow plugin

A minimal, working example of both kinds of SynthFlow plugin SynthFlow
currently supports — copy this directory as a starting point for your
own.

## What it does

- Registers one new preset, `license_plate`, that a STRING field can use
  instead of `faker.word()` or a built-in preset like `pan`/`vin`.
- Registers one new rule function, `is_business_day`, callable by name
  from inside a rule condition, an event-trigger condition, or a formula
  field — the same way the built-in `noise()`/`uniform()` already are.

## How it works

SynthFlow's backend discovers both kinds of plugin via Python's standard
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
mechanism — the same approach pytest, Flask, and many other tools use for
plugins. Any package installed into the same environment as the backend
that declares an entry under one of SynthFlow's two entry-point groups is
picked up automatically:

```toml
[project.entry-points."synthflow.generators"]
license_plate = "synthflow_example_plugin.generators:license_plate"

[project.entry-points."synthflow.rule_functions"]
is_business_day = "synthflow_example_plugin.rule_functions:is_business_day"
```

The right-hand side is `module.path:function_name`.

- A **generator** function must take no arguments and return a
  JSON-serializable value (`str`, `int`, `float`, `bool`, `list`, or
  `dict`) — see `generators.py`.
- A **rule function** can take any number of positional arguments
  (whatever the expression calling it passes) and return whatever the
  evaluator can use — a `bool` for a rule/event-trigger condition, a
  number for a formula — see `rule_functions.py`.

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

To remove it: `pip uninstall synthflow-example-plugin` and restart the
backend again.

## Notes for a real plugin

- A plugin's name can't shadow a built-in name (`pan`, `vin`,
  `nginx_access_log`, `noise`, `uniform`, etc.) — a colliding name is
  skipped, with a warning logged, so a plugin can never silently
  redefine what a built-in means.
- A plugin is arbitrary Python code that runs with the same privileges
  as the backend process — there's no sandboxing. Only install plugins
  you trust, the same as any other Python dependency.
- See `app/services/plugins.py` in the main repo for the discovery code
  itself, and `app/services/expressions.py` for how a rule function gets
  called from inside an expression.
