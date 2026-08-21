"""The generator half of Phase 5's "formal plugin framework" — the other
three categories on the roadmap (output, rule, AI provider plugins) are
deliberately not started here; see ROADMAP.md for why generator plugins
were the first cut.

A generator plugin is any installed Python package that declares one or
more zero-argument callables under the `synthflow.generators` entry-point
group, e.g. in the plugin's own pyproject.toml:

    [project.entry-points."synthflow.generators"]
    my_preset = "my_package.generators:my_preset_fn"

`my_preset_fn` must take no arguments and return a JSON-serializable value
(str, int, float, bool, list, or dict) — the same contract the built-in
LogPreset/IdentifierPreset generators already follow (see
app.services.log_generators / app.services.identifier_generators): no row
context, since presets are resolved independently of the rest of the row
being generated (app.services.generator._generate_value). Once installed
(`pip install my-plugin-package`) into the same environment as the
backend, "my_preset" appears automatically wherever a preset name is
accepted — no SynthFlow code change, no restart-time registration step
beyond the process restart that picking up a newly installed package
always requires.

Security note: a generator plugin is arbitrary Python code that runs with
the same privileges as the backend process — there is no sandboxing. This
is the same trust model as installing any pip package into this
environment; it is the deployer's responsibility to only install plugins
they trust, the same way they'd vet any other dependency.

Versioning: PLUGIN_API_VERSION exists so a future breaking change to the
contract above has something to check plugins against. There's nothing to
check yet in v1 — every zero-arg callable is accepted — but the constant
is here now so a v2 change doesn't have to retrofit one in.
"""

import logging
from collections.abc import Callable
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from app.models.field import IdentifierPreset, LogPreset
from app.services.identifier_generators import generate_identifier
from app.services.log_generators import generate_log_line

logger = logging.getLogger(__name__)

PLUGIN_API_VERSION = 1
ENTRY_POINT_GROUP = "synthflow.generators"

GeneratorPlugin = Callable[[], Any]


def _builtin_generators() -> dict[str, GeneratorPlugin]:
    registry: dict[str, GeneratorPlugin] = {}
    for preset in LogPreset:
        registry[preset.value] = lambda p=preset.value: generate_log_line(p)
    for preset in IdentifierPreset:
        registry[preset.value] = lambda p=preset.value: generate_identifier(p)
    return registry


def _load_plugin(entry_point: EntryPoint) -> GeneratorPlugin | None:
    try:
        fn = entry_point.load()
    except Exception:
        logger.warning("Failed to load generator plugin '%s'", entry_point.name, exc_info=True)
        return None
    if not callable(fn):
        logger.warning("Generator plugin '%s' did not resolve to a callable", entry_point.name)
        return None
    return fn


def _discovered_plugins() -> dict[str, tuple[GeneratorPlugin, str]]:
    """Third-party generator plugins found via entry-point discovery, keyed
    by name, alongside the distribution name they came from (for
    `list_available_presets`'s `source` field). A plugin whose name
    collides with a built-in preset is skipped — a plugin cannot silently
    redefine what "pan" or "nginx_access_log" means."""
    builtins = _builtin_generators()
    discovered: dict[str, tuple[GeneratorPlugin, str]] = {}
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        if entry_point.name in builtins or entry_point.name in discovered:
            logger.warning(
                "Generator plugin '%s' from '%s' skipped — name already in use",
                entry_point.name,
                entry_point.dist.name if entry_point.dist else "?",
            )
            continue
        fn = _load_plugin(entry_point)
        if fn is not None:
            dist_name = entry_point.dist.name if entry_point.dist else "unknown"
            discovered[entry_point.name] = (fn, dist_name)
    return discovered


def available_presets() -> dict[str, GeneratorPlugin]:
    """Every preset name currently usable in a field's `preset` column —
    built-in first, then whatever third-party plugins are installed."""
    registry = _builtin_generators()
    for name, (fn, _dist) in _discovered_plugins().items():
        registry[name] = fn
    return registry


def list_available_presets() -> list[dict[str, str]]:
    """The same registry as `available_presets`, shaped for the
    `GET /generator-plugins` API response the frontend uses to render the
    preset picker without hardcoding preset names — see
    app.api.routes.generator_plugins."""
    presets = [{"name": p.value, "source": "builtin", "category": "log"} for p in LogPreset]
    presets += [
        {"name": p.value, "source": "builtin", "category": "identifier"} for p in IdentifierPreset
    ]
    for name, (_fn, dist_name) in _discovered_plugins().items():
        presets.append({"name": name, "source": f"plugin:{dist_name}", "category": "plugin"})
    return presets


def generate_preset_value(preset: str) -> Any:
    registry = available_presets()
    if preset not in registry:
        raise ValueError(f"Unknown preset '{preset}'")
    return registry[preset]()
