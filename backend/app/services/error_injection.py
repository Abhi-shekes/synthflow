"""Validation for error-injection configs: which corruption types make sense
for a given field type. The actual corruption happens in
app.services.generator._corrupt_value — see app.models.error_injection for
the full picture, including its interaction with rules.
"""

from app.models.error_injection import ErrorType
from app.models.field import FieldType

_TYPE_RESTRICTIONS: dict[ErrorType, set[FieldType] | None] = {
    ErrorType.NULL: None,
    ErrorType.DUPLICATE: None,
    ErrorType.WRONG_TYPE: None,
    ErrorType.EMPTY: {FieldType.STRING, FieldType.ARRAY, FieldType.OBJECT, FieldType.JSON},
    ErrorType.TRUNCATE: {FieldType.STRING},
    ErrorType.OUT_OF_RANGE: {FieldType.INTEGER, FieldType.FLOAT},
}


def validate_error_types(field_type: FieldType, error_types: list[ErrorType]) -> None:
    if not error_types:
        raise ValueError("error_types cannot be empty")
    for error_type in error_types:
        allowed = _TYPE_RESTRICTIONS[error_type]
        if allowed is not None and field_type not in allowed:
            raise ValueError(f"'{error_type}' is not valid for field type '{field_type}'")
