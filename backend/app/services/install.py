"""What this particular SynthFlow install can actually do.

The roadmap's "modular installation" idea is that a Kafka-only
deployment shouldn't pull MQTT's dependencies at all. That's real here,
not cosmetic: `aiokafka` and `aiomqtt` live in optional extras
(see pyproject.toml), so `pip install .[kafka]` genuinely leaves aiomqtt
off the machine.

Which means the code has to cope with them being absent. Three rules:

1. Nothing imports a broker client at module scope — `stream_producers`
   imports inside the loop that needs it, so the module still imports on
   a install where neither extra is present.
2. Creating an output whose extra is missing fails fast with a clear 400
   naming the extra to install, rather than a 500 or a background task
   that dies on its first tick.
3. `GET /install-config` reports this, so the Web UI can grey out an
   output it can't offer and say why instead of showing a control that
   would just error.

Detection is `importlib.util.find_spec`, deliberately not a real import:
this is called per request and on the entity page load, and importing
aiokafka for real is slow enough to notice. find_spec only checks the
module is locatable.
"""

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    """One optionally-installed capability."""

    key: str
    module: str
    extra: str
    label: str
    description: str


FEATURES: tuple[Feature, ...] = (
    Feature(
        key="kafka",
        module="aiokafka",
        extra="kafka",
        label="Kafka output",
        description="Publish generated rows to a Kafka topic.",
    ),
    Feature(
        key="mqtt",
        module="aiomqtt",
        extra="mqtt",
        label="MQTT output",
        description="Publish generated rows to an MQTT broker.",
    ),
    Feature(
        key="mysql",
        module="pymysql",
        extra="mysql",
        label="MySQL push",
        description="Write generated rows into a MySQL database.",
    ),
    Feature(
        key="mongo",
        module="pymongo",
        extra="mongo",
        label="MongoDB push",
        description="Write generated rows into a MongoDB collection.",
    ),
)

_FEATURES_BY_KEY = {feature.key: feature for feature in FEATURES}


def is_available(key: str) -> bool:
    feature = _FEATURES_BY_KEY.get(key)
    if feature is None:
        raise ValueError(f"Unknown feature '{key}'")
    return importlib.util.find_spec(feature.module) is not None


def require(key: str) -> None:
    """Raise with an actionable message if an optional feature is missing.
    Callers turn this into a 400 — see app.api.routes.kafka_outputs."""
    if not is_available(key):
        feature = _FEATURES_BY_KEY[key]
        raise ValueError(
            f"{feature.label} is not available in this install: the optional "
            f"'{feature.extra}' extra isn't installed. Reinstall the backend with "
            f"pip install '.[{feature.extra}]' (or set SYNTHFLOW_EXTRAS={feature.extra} "
            f"and rebuild the container) to enable it."
        )


def describe() -> list[dict[str, object]]:
    """Shaped for `GET /install-config`."""
    return [
        {
            "key": feature.key,
            "label": feature.label,
            "description": feature.description,
            "extra": feature.extra,
            "available": is_available(feature.key),
        }
        for feature in FEATURES
    ]
