# Example SynthFlow generator plugin

A minimal, working example of a SynthFlow generator plugin — copy this
directory as a starting point for your own.

## What it does

Registers one new preset, `license_plate`, that a STRING field can use
instead of `faker.word()` or a built-in preset like `pan`/`vin`.

## How it works

SynthFlow's backend discovers generator plugins via Python's standard
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
mechanism — the same approach pytest, Flask, and many other tools use for
plugins. Any package installed into the same environment as the backend
that declares an entry under the `synthflow.generators` group is picked
up automatically:

```toml
[project.entry-points."synthflow.generators"]
license_plate = "synthflow_example_plugin.generators:license_plate"
```

The right-hand side is `module.path:function_name`. The function must
take no arguments and return a JSON-serializable value (`str`, `int`,
`float`, `bool`, `list`, or `dict`) — see `generators.py` for the
implementation.

## Trying it

From the SynthFlow backend's own environment (wherever `app/main.py`
runs):

```bash
pip install -e /path/to/examples/example-generator-plugin
```

Restart the backend process so it re-discovers installed entry points,
then:

- `GET /api/v1/generator-plugins` now includes `license_plate` with
  `"category": "plugin"`.
- Create a STRING field with `"preset": "license_plate"` — generated
  rows will contain values like `"AB12 CDE"`.

To remove it: `pip uninstall synthflow-example-plugin` and restart the
backend again.

## Notes for a real plugin

- A plugin's name can't shadow a built-in preset name (`pan`, `vin`,
  `nginx_access_log`, etc.) — a colliding name is skipped, with a
  warning logged, so a plugin can never silently redefine what a
  built-in preset means.
- A plugin is arbitrary Python code that runs with the same privileges
  as the backend process — there's no sandboxing. Only install plugins
  you trust, the same as any other Python dependency.
- See `app/services/plugins.py` in the main repo for the discovery code
  itself.
