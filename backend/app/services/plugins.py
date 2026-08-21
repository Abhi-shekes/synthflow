"""Two of Phase 5's "formal plugin framework" categories — output and AI
provider plugins are deliberately not started here; see ROADMAP.md for
why generator and rule-function plugins were the two cuts taken.

A **generator plugin** is any installed Python package that declares one
or more zero-argument callables under the `synthflow.generators`
entry-point group:

    [project.entry-points."synthflow.generators"]
    my_preset = "my_package.generators:my_preset_fn"

`my_preset_fn` must take no arguments and return a JSON-serializable value
(str, int, float, bool, list, or dict) — the same contract the built-in
LogPreset/IdentifierPreset generators already follow (see
app.services.log_generators / app.services.identifier_generators): no row
context, since presets are resolved independently of the rest of the row
being generated (app.services.generator._generate_value). Once installed
"my_preset" appears wherever a preset name is accepted.

A **rule-function plugin** is the same idea for
app.services.expressions.evaluate: any installed package that declares a
callable under `synthflow.rule_functions` becomes callable *by name* from
inside any rule condition, event-trigger condition, or formula field, the
same way the built-in `noise()`/`uniform()` already are:

    [project.entry-points."synthflow.rule_functions"]
    is_business_day = "my_package.rules:is_business_day"

Unlike a generator plugin, a rule function can take any number of
positional arguments (whatever the expression passes it) and return
anything the evaluator can use — a bool for a rule condition, a number
for a formula. expressions.py does the actual name lookup/dispatch (see
its `_FUNCTIONS` dict and evaluate()'s Call handling) — this module only
does discovery, so expressions.py doesn't have to know how entry points
work and this module doesn't have to import expressions.py (its built-in
function names live there, not here, to avoid a circular import; a
plugin function collides with a built-in exactly the same way — built-in
wins — the check just happens in expressions.py instead of here).

Both kinds are discovered fresh on every call, not cached: a newly
`pip install`ed plugin needs the *process* to restart before an
already-running worker sees it (a filesystem-level cost, not something
caching this module's own lookups would avoid or fix — see the plugin
framework round's live-verification notes), but nothing here prevents
picking it up sooner in a batch generation loop, at the cost of
re-scanning entry points on every value/expression call that uses one.
Left unoptimized deliberately: only expressions that actually call a
plugin function pay this cost, and profiling a real slowdown before
adding a cache beats guessing at one.

Security note: a plugin is arbitrary Python code that runs with the same
privileges as the backend process — there is no sandboxing. This is the
same trust model as installing any pip package into this environment; it
is the deployer's responsibility to only install plugins they trust, the
same way they'd vet any other dependency.

Versioning: PLUGIN_API_VERSION exists so a future breaking change to
either contract above has something to check plugins against. There's
nothing to check yet in v1 — but the constant is here now so a v2 change
doesn't have to retrofit one in.
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
RULE_FUNCTION_ENTRY_POINT_GROUP = "synthflow.rule_functions"

GeneratorPlugin = Callable[[], Any]
RuleFunction = Callable[..., Any]


def _builtin_generators() -> dict[str, GeneratorPlugin]:
    registry: dict[str, GeneratorPlugin] = {}
    for preset in LogPreset:
        registry[preset.value] = lambda p=preset.value: generate_log_line(p)
    for preset in IdentifierPreset:
        registry[preset.value] = lambda p=preset.value: generate_identifier(p)
    return registry


def _load_entry_point(entry_point: EntryPoint, kind: str) -> Callable | None:
    try:
        fn = entry_point.load()
    except Exception:
        logger.warning("Failed to load %s '%s'", kind, entry_point.name, exc_info=True)
        return None
    if not callable(fn):
        logger.warning("%s '%s' did not resolve to a callable", kind, entry_point.name)
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
        fn = _load_entry_point(entry_point, "generator plugin")
        if fn is not None:
            dist_name = entry_point.dist.name if entry_point.dist else "unknown"
            discovered[entry_point.name] = (fn, dist_name)
    return discovered


def _discovered_rule_functions() -> dict[str, tuple[RuleFunction, str]]:
    """Third-party rule/expression functions found via entry-point
    discovery. Collision handling against the *built-in* function names
    (abs/min/max/round/len/noise/uniform) happens in expressions.py, not
    here — see this module's docstring for why — but a rule-function
    plugin colliding with *another* rule-function plugin is still caught
    here, same as generator plugins."""
    discovered: dict[str, tuple[RuleFunction, str]] = {}
    for entry_point in entry_points(group=RULE_FUNCTION_ENTRY_POINT_GROUP):
        if entry_point.name in discovered:
            logger.warning(
                "Rule function '%s' from '%s' skipped — name already in use",
                entry_point.name,
                entry_point.dist.name if entry_point.dist else "?",
            )
            continue
        fn = _load_entry_point(entry_point, "rule function")
        if fn is not None:
            dist_name = entry_point.dist.name if entry_point.dist else "unknown"
            discovered[entry_point.name] = (fn, dist_name)
    return discovered


def available_rule_functions() -> dict[str, RuleFunction]:
    """Third-party functions callable by name from a rule/event-trigger
    condition or a formula — see app.services.expressions.evaluate. Does
    NOT include the built-ins (those live in expressions.py); the caller
    there merges the two, built-ins winning any name collision."""
    return {name: fn for name, (fn, _dist) in _discovered_rule_functions().items()}


def list_available_rule_functions() -> list[dict[str, str]]:
    """Plugin-sourced rule functions only, shaped for
    `GET /rule-functions` — see app.api.routes.rule_functions, which
    merges this with expressions.BUILTIN_FUNCTIONS for the full picture."""
    return [
        {"name": name, "source": f"plugin:{dist_name}"}
        for name, (_fn, dist_name) in _discovered_rule_functions().items()
    ]


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
