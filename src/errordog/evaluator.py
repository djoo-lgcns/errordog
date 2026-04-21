"""Expression evaluation against ESF snapshot frame locals."""

import ast
from pathlib import Path
from typing import Any

import coredumpy


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
    """Evaluate a Python expression against reconstructed frame locals (ESF fallback).

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


def eval_expression_coredumpy(
    expression: str, dump_path: str, frame_index: int = 0
) -> dict:
    """Evaluate a Python expression against a coredumpy dump (full fidelity).

    Returns a dict with: success, result, error, mode.
    """
    data = coredumpy.Coredumpy.load_data_from_path(dump_path)
    frame = data["frame"]

    # Walk to the requested frame index
    frames: list[Any] = []
    current = frame
    while current is not None:
        frames.append(current)
        current = getattr(current, "f_back", None)

    if frame_index < 0 or frame_index >= len(frames):
        return {
            "success": False,
            "result": None,
            "error": f"Frame index {frame_index} out of range (0..{len(frames) - 1})",
            "unavailable_vars": [],
        }

    target = frames[frame_index]
    try:
        result = eval(expression, target.f_globals, target.f_locals)
        return {
            "success": True,
            "result": repr(result),
            "error": None,
            "unavailable_vars": [],
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": f"{type(e).__name__}: {e}",
            "unavailable_vars": [],
        }
