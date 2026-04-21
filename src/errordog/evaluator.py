"""Expression evaluation against ESF snapshot frame locals."""

import ast
from typing import Any


def reconstruct_namespace(
    frame_locals: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    """Parse repr strings back to Python values via ast.literal_eval.

    Returns:
        (namespace, unavailable_vars) — namespace contains successfully parsed
        values; unavailable_vars lists names that could not be parsed.
    """
    namespace: dict[str, Any] = {}
    unavailable: list[str] = []
    for name, repr_str in frame_locals.items():
        try:
            namespace[name] = ast.literal_eval(repr_str)
        except (ValueError, SyntaxError):
            unavailable.append(name)
    return namespace, unavailable


def eval_expression(expression: str, frame_locals: dict[str, str]) -> dict:
    """Evaluate a Python expression against reconstructed frame locals.

    Returns a dict with: success, result, error, unavailable_vars.
    """
    namespace, unavailable = reconstruct_namespace(frame_locals)
    try:
        result = eval(expression, {"__builtins__": __builtins__}, namespace)
        return {
            "success": True,
            "result": repr(result),
            "error": None,
            "unavailable_vars": unavailable,
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": f"{type(e).__name__}: {e}",
            "unavailable_vars": unavailable,
        }
