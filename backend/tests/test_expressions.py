import pytest

from app.services.expressions import ExpressionError, evaluate


def test_arithmetic():
    assert evaluate("price * quantity", {"price": 4, "quantity": 3}) == 12
    assert evaluate("(price + 1) / 2", {"price": 3}) == 2


def test_comparisons_and_boolean_logic():
    assert evaluate("price > 0 and price < 100", {"price": 50}) is True
    assert evaluate("price > 0 and price < 100", {"price": 150}) is False
    assert evaluate("1000 <= volume <= 50000", {"volume": 2000}) is True
    assert evaluate("status == 'active' or status == 'pending'", {"status": "pending"}) is True


def test_ternary():
    assert evaluate("'weekday' if day < 5 else 'weekend'", {"day": 6}) == "weekend"


def test_whitelisted_functions():
    assert evaluate("max(a, b)", {"a": 3, "b": 7}) == 7
    assert evaluate("round(price, 2)", {"price": 1.005}) == 1.0


def test_unknown_variable_raises():
    with pytest.raises(ExpressionError):
        evaluate("missing + 1", {})


def test_disallows_attribute_access():
    with pytest.raises(ExpressionError):
        evaluate("x.__class__", {"x": 1})


def test_disallows_arbitrary_calls():
    with pytest.raises(ExpressionError):
        evaluate("__import__('os')", {})


def test_disallows_subscript():
    with pytest.raises(ExpressionError):
        evaluate("x[0]", {"x": [1, 2]})


def test_invalid_syntax_raises():
    with pytest.raises(ExpressionError):
        evaluate("price >", {"price": 1})
