"""Validation shared by every path that can create/update an
EntityField: the normal `POST/PATCH .../fields` routes
(app.api.routes.entities) and template import (app.services.templates).
Both raise ValueError rather than HTTPException, since template import
has no HTTP request to attach a status code to — each caller converts it
to a 400 itself.
"""

from app.models.field import FieldType
from app.services.plugins import available_presets


def validate_enum_weights(
    field_type: FieldType, enum_values: list[str] | None, enum_weights: list[float] | None
) -> None:
    if enum_weights is None:
        return
    if field_type != FieldType.ENUM:
        raise ValueError("enum_weights can only be set on enum fields")
    if not enum_values:
        raise ValueError("enum_weights requires enum_values")
    if len(enum_weights) != len(enum_values):
        raise ValueError("enum_weights must have the same length as enum_values")
    if any(w < 0 for w in enum_weights):
        raise ValueError("enum_weights must be non-negative")
    if sum(enum_weights) <= 0:
        raise ValueError("at least one enum_weight must be greater than 0")


def validate_preset(field_type: FieldType, preset: str | None, regex: str | None) -> None:
    if preset is None:
        return
    if field_type != FieldType.STRING:
        raise ValueError("preset can only be set on string fields")
    if regex:
        raise ValueError(
            "preset and regex are mutually exclusive — preset fully determines the value"
        )
    if preset not in available_presets():
        raise ValueError(f"Unknown preset '{preset}'")
