"""A small, safe expression evaluator for formula fields and validation rules.

Deliberately not `eval()`: this walks a restricted subset of the Python AST —
arithmetic, comparisons, boolean logic, a ternary, and a short whitelist of
functions — so a user-authored expression can only read the variables handed
to it and can never reach attribute access, subscripting, imports, or
arbitrary calls.

`noise` and `uniform` are the two non-pure functions in the whitelist — they
exist specifically so a formula field can express a *correlation* with
realistic scatter instead of a perfectly deterministic line, e.g.
`humidity = 100 - temperature * 0.8 + noise(3)`. This is same-row,
same-entity correlation — a formula can already reference any
earlier-ordered field on its own row (that's the whole formula-field
mechanism, not something new here).

Cross-entity references (`Customer.age` from an `Order` formula/rule, when
a Relationship connects the two) reuse that same "already in `variables`"
model rather than adding a second mechanism: `ast.Attribute` is allowed,
but *only* one level deep on a name that already resolves to a plain dict
already present in `variables` — never real attribute/method access on an
actual object. `app.services.generator` is what puts a related entity's
linked row into `variables` under that entity's name in the first place;
this evaluator only needs to know how to read one field off of it once
it's there. See Relationship's docstring and generator.py's
`relationship_lookup`/`cross-entity` handling for how the *specific*
linked row (not just any row of that entity) ends up there.

Beyond the built-in whitelist, a call can also reach a name registered by
an installed rule-function plugin (see app.services.plugins — the
"synthflow.rule_functions" entry-point group) — the plugin half of
Phase 5's formal plugin framework that isn't a generator: a
`luhn_valid(card_number)` or `is_business_day(order_date)` a project
author installed becomes callable here by name, exactly like `noise()`
is. A plugin function can't shadow a built-in name; the built-in wins.
"""

import ast
import operator
import random
from typing import Any

from app.services.plugins import available_rule_functions

_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}
_COMPARE_OPS: dict[type, Any] = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "len": len,
    "noise": lambda stddev: random.gauss(0, stddev),
    "uniform": random.uniform,
}

BUILTIN_FUNCTIONS = sorted(_FUNCTIONS)


class ExpressionError(ValueError):
    pass


def evaluate(expr: str, variables: dict[str, Any]) -> Any:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid expression '{expr}': {exc.msg}") from exc
    return _eval(tree.body, variables)


def _eval(node: ast.AST, variables: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ExpressionError(f"Unknown variable '{node.id}'")
        return variables[node.id]

    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ExpressionError(f"Operator '{type(node.op).__name__}' is not allowed")
        return op(_eval(node.left, variables), _eval(node.right, variables))

    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise ExpressionError(f"Operator '{type(node.op).__name__}' is not allowed")
        return op(_eval(node.operand, variables))

    if isinstance(node, ast.BoolOp):
        values = [_eval(v, variables) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)

    if isinstance(node, ast.Compare):
        left = _eval(node.left, variables)
        for op_node, comparator in zip(node.ops, node.comparators, strict=True):
            op = _COMPARE_OPS.get(type(op_node))
            if op is None:
                raise ExpressionError(f"Comparison '{type(op_node).__name__}' is not allowed")
            right = _eval(comparator, variables)
            if not op(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.Attribute):
        base = _eval(node.value, variables)
        if not isinstance(base, dict):
            raise ExpressionError(f"'.{node.attr}' can only follow a related entity's name")
        if node.attr not in base:
            raise ExpressionError(f"Unknown variable '{node.attr}'")
        return base[node.attr]

    if isinstance(node, ast.IfExp):
        branch = node.body if _eval(node.test, variables) else node.orelse
        return _eval(branch, variables)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only direct function calls are allowed")
        func_name = node.func.id
        if func_name in _FUNCTIONS:
            fn = _FUNCTIONS[func_name]
        else:
            plugin_functions = available_rule_functions()
            if func_name not in plugin_functions:
                allowed = ", ".join(sorted(_FUNCTIONS.keys() | plugin_functions.keys()))
                raise ExpressionError(f"Only these functions are allowed: {allowed}")
            fn = plugin_functions[func_name]
        if node.keywords:
            raise ExpressionError("Keyword arguments are not allowed")
        args = [_eval(a, variables) for a in node.args]
        try:
            return fn(*args)
        except ExpressionError:
            raise
        except Exception as exc:
            # A built-in or plugin function can raise anything (a plugin's
            # date.fromisoformat on a value it doesn't like, say) — never
            # let that escape as a raw 500, especially since the *dummy*
            # values used to validate a condition at creation time
            # (app.api.routes.entities.dummy_row_values) are only a
            # best-effort stand-in for what a real row will contain.
            raise ExpressionError(f"'{func_name}(...)' raised an error: {exc}") from exc

    raise ExpressionError(f"Expression contains unsupported syntax: {type(node).__name__}")
