"""Errordog MCP server with tools for error snapshot management."""

from pathlib import Path

from fastmcp import FastMCP

from errordog.evaluator import eval_expression
from errordog.store import SnapshotStore
from errordog.testgen import generate_reproduction_test as _generate_test

mcp = FastMCP("errordog")

_store: SnapshotStore | None = None


def _get_store() -> SnapshotStore:
    global _store
    if _store is None:
        _store = SnapshotStore()
    return _store


@mcp.tool()
def list_errors() -> list[dict]:
    """Return list of stored error snapshots with summary info.

    Each entry includes: error_id, timestamp, exception_type,
    exception_message, file_path, line_number, function_name.
    Sorted by timestamp descending (most recent first).
    """
    store = _get_store()
    summaries = store.list_summaries()
    return [s.model_dump() for s in summaries]


@mcp.tool()
def get_error_details(error_id: str) -> dict:
    """Return full ESF JSON data for a specific error snapshot.

    Args:
        error_id: The unique error identifier (e.g., err_20260310T131600_a3f2b1).

    Returns:
        Full snapshot data or error message dict if not found.
    """
    store = _get_store()
    try:
        snapshot = store.get_snapshot(error_id)
        return snapshot.model_dump()
    except FileNotFoundError:
        return {"error": "Snapshot not found", "error_id": error_id}
    except ValueError:
        return {"error": "Snapshot corrupted", "error_id": error_id}


@mcp.tool()
def evaluate_expression(
    expression: str, error_id: str, frame_index: int = 0
) -> dict:
    """Evaluate a Python expression against the locals of a snapshot frame.

    Reconstructs the namespace from stored repr strings via ast.literal_eval,
    then runs eval(). Variables that cannot be parsed are silently skipped.

    Args:
        expression: Python expression to evaluate (e.g., "len(items)").
        error_id: The snapshot to evaluate against.
        frame_index: Stack frame index (0 = crash point).

    Returns:
        Dict with success, result, error, unavailable_vars, mode.
    """
    store = _get_store()
    try:
        snapshot = store.get_snapshot(error_id)
    except FileNotFoundError:
        return {"success": False, "error": f"Snapshot not found: {error_id}"}
    except ValueError:
        return {"success": False, "error": f"Snapshot corrupted: {error_id}"}

    if frame_index < 0 or frame_index >= len(snapshot.frames):
        return {
            "success": False,
            "error": f"Frame index {frame_index} out of range (0..{len(snapshot.frames) - 1})",
        }

    frame = snapshot.frames[frame_index]
    result = eval_expression(expression, frame.locals)
    result["mode"] = "mock"
    return result


@mcp.tool()
def generate_reproduction_test(error_id: str) -> dict:
    """Generate a pytest script that reproduces the error from a snapshot.

    Extracts the function name and arguments from the top stack frame,
    and writes a test to ~/.errordog/generated_tests/.

    Args:
        error_id: The snapshot to generate a test from.

    Returns:
        Dict with error_id, test_code, file_path, function_name, exception_type.
    """
    store = _get_store()
    return _generate_test(error_id, store=store)


def create_server(snapshot_dir: Path | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance with tools registered."""
    global _store
    _store = SnapshotStore(snapshot_dir=snapshot_dir)
    return mcp
