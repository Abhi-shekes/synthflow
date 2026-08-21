"""Trend value functions: a numeric field's value as a function of its row's
0-indexed position within the current batch, optionally with gaussian noise
on top. See app.models.trend.Trend's docstring for what "position" means and
its known limitations (resets each generate call, random_walk + rules).
"""

import math
import random
from typing import Any

from app.models.trend import Trend, TrendType

REQUIRED_PARAMS: dict[TrendType, set[str]] = {
    TrendType.LINEAR: {"start", "slope"},
    TrendType.EXPONENTIAL: {"start", "rate"},
    TrendType.LOGISTIC: {"capacity", "rate", "midpoint"},
    TrendType.SEASONAL: {"base", "amplitude", "period"},
    TrendType.CYCLIC: {"base", "amplitude", "period"},
    TrendType.RANDOM_WALK: {"start", "step_size"},
}
OPTIONAL_PARAMS = {"noise"}


def validate_params(trend_type: TrendType, params: dict[str, Any]) -> None:
    required = REQUIRED_PARAMS[trend_type]
    missing = required - params.keys()
    if missing:
        raise ValueError(f"{trend_type} requires params: {', '.join(sorted(missing))}")
    extra = params.keys() - required - OPTIONAL_PARAMS
    if extra:
        raise ValueError(f"Unknown params for {trend_type}: {', '.join(sorted(extra))}")
    if not all(isinstance(v, (int, float)) for v in params.values()):
        raise ValueError("All trend params must be numbers")
    if trend_type in (TrendType.SEASONAL, TrendType.CYCLIC) and params["period"] == 0:
        raise ValueError("period must not be zero")
    if trend_type == TrendType.RANDOM_WALK and params["step_size"] < 0:
        raise ValueError("step_size must not be negative")


def _value_at(trend_type: TrendType, position: int, params: dict[str, float], state: dict) -> float:
    if trend_type == TrendType.LINEAR:
        return params["start"] + params["slope"] * position

    if trend_type == TrendType.EXPONENTIAL:
        return params["start"] * math.exp(params["rate"] * position)

    if trend_type == TrendType.LOGISTIC:
        return params["capacity"] / (
            1 + math.exp(-params["rate"] * (position - params["midpoint"]))
        )

    if trend_type in (TrendType.SEASONAL, TrendType.CYCLIC):
        return params["base"] + params["amplitude"] * math.sin(
            2 * math.pi * position / params["period"]
        )

    if trend_type == TrendType.RANDOM_WALK:
        if "value" not in state:
            state["value"] = params["start"]
        else:
            state["value"] += random.uniform(-params["step_size"], params["step_size"])
        return state["value"]

    raise ValueError(f"Unsupported trend type: {trend_type}")


def generate_trend_value(trend: Trend, position: int, state: dict) -> float:
    value = _value_at(trend.trend_type, position, trend.params, state)
    noise = trend.params.get("noise")
    if noise:
        value += random.gauss(0, noise)
    return value
