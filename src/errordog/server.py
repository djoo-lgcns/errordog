"""Errordog MCP server with tools for error snapshot management."""

from pathlib import Path

from fastmcp import FastMCP

from errordog.dap.mock import MockAdapter
from errordog.evaluator import eval_expression, eval_expression_coredumpy
from errordog.store import SnapshotStore
from errordog.testgen import generate_reproduction_test as _generate_test

mcp = FastMCP("errordog")

_store: SnapshotStore | None = None
_adapters: dict[str, MockAdapter] = {}


def _get_store() -> SnapshotStore:
    global _store
    if _store is None:
        _store = SnapshotStore()
    return _store


def _get_adapter(error_id: str) -> MockAdapter | None:
    """Return a cached MockAdapter for post-mortem DAP inspection."""
    if error_id not in _adapters:
        store = _get_store()
        adapter = MockAdapter(error_id, snapshot_dir=store.snapshot_dir)
        if not adapter._load():
            return None
        _adapters[error_id] = adapter
    return _adapters[error_id]


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

    # Coredumpy path: full-fidelity eval against real objects
    if snapshot.dump_path and Path(snapshot.dump_path).exists():
        try:
            result = eval_expression_coredumpy(expression, snapshot.dump_path, frame_index)
            result["mode"] = "coredumpy"
            return result
        except Exception:
            pass  # fall through to ESF

    # ESF fallback: repr-based reconstruction
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


@mcp.tool()
def dap_get_stack_frames(error_id: str) -> list[dict]:
    """Get stack frames for post-mortem DAP inspection of a snapshot.

    Returns frames with frame_index values for use in dap_get_variables.
    frame_index=0 is the crash point (innermost frame).

    Args:
        error_id: The snapshot to inspect.

    Returns:
        List of {frame_index, function_name, file_path, line_number},
        or [{"error": "..."}] if snapshot not found.
    """
    adapter = _get_adapter(error_id)
    if adapter is None:
        return [{"error": f"Snapshot not found: {error_id}"}]
    return [
        {
            "frame_index": frame.id,
            "function_name": frame.name,
            "file_path": frame.source_path,
            "line_number": frame.line,
        }
        for frame in adapter.session.stack_trace
    ]


@mcp.tool()
def dap_get_variables(error_id: str, frame_index: int = 0) -> list[dict]:
    """Get variables for a specific stack frame in post-mortem mode.

    If a variable's variablesReference > 0, it is a nested object (dict, list, tuple).
    Call dap_drill_into() with that reference to expand it.

    Args:
        error_id: The snapshot to inspect.
        frame_index: Stack frame index (0 = crash point, from dap_get_stack_frames).

    Returns:
        List of {name, value, type, variablesReference},
        or [{"error": "..."}] if snapshot or frame not found.
    """
    adapter = _get_adapter(error_id)
    if adapter is None:
        return [{"error": f"Snapshot not found: {error_id}"}]
    variables = adapter.session.variables.get(frame_index)
    if variables is None:
        return [{"error": f"Frame index {frame_index} not found"}]
    return [
        {
            "name": v.name,
            "value": v.value,
            "type": v.type or "",
            "variablesReference": v.variables_reference,
        }
        for v in variables
    ]


@mcp.tool()
def dap_drill_into(error_id: str, variables_reference: int) -> list[dict]:
    """Drill into a nested object using its variablesReference.

    Obtain the variablesReference from dap_get_variables() or a previous
    dap_drill_into() call. Returns [] if the reference is not expandable.

    Args:
        error_id: The snapshot to inspect.
        variables_reference: The reference integer from a previous dap_get_variables
            or dap_drill_into call. Must be > 0.

    Returns:
        List of {name, value, type, variablesReference} for the nested object's fields,
        or [] if reference is unknown or not expandable.
    """
    adapter = _get_adapter(error_id)
    if adapter is None:
        return [{"error": f"Snapshot not found: {error_id}"}]
    return adapter._drilldown.get(variables_reference, [])


def create_server(snapshot_dir: Path | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance with tools registered."""
    global _store, _adapters
    _store = SnapshotStore(snapshot_dir=snapshot_dir)
    _adapters.clear()
    return mcp
