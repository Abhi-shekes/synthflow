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
same-entity correlation only: a formula can already reference any
earlier-ordered field on its own row (that's the whole formula-field
mechanism, not something new here), but it still can't see another entity's
data — cross-entity correlation needs the same extension cross-entity rules
would (see TODO.md), not built yet.
"""

import ast
import operator
import random
from typing import Any

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

    if isinstance(node, ast.IfExp):
        branch = node.body if _eval(node.test, variables) else node.orelse
        return _eval(branch, variables)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            allowed = ", ".join(sorted(_FUNCTIONS))
            raise ExpressionError(f"Only these functions are allowed: {allowed}")
        if node.keywords:
            raise ExpressionError("Keyword arguments are not allowed")
        args = [_eval(a, variables) for a in node.args]
        return _FUNCTIONS[node.func.id](*args)

    raise ExpressionError(f"Expression contains unsupported syntax: {type(node).__name__}")
