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
    """List captured Python error snapshots. Call this first if no error_id is known.

    Each entry includes: error_id, timestamp, exception_type,
    exception_message, file_path, line_number, function_name.
    Sorted by timestamp descending (most recent first).

    Once you have an error_id, call inspect_error(error_id) to investigate.
    """
    store = _get_store()
    summaries = store.list_summaries()
    return [s.model_dump() for s in summaries]


@mcp.tool()
def get_error_details(error_id: str) -> dict:
    """Return the full raw ESF JSON for a snapshot. Use inspect_error() for debugging.

    Do NOT call this for interactive error diagnosis — inspect_error() returns
    pre-parsed stack frames and variables in a concise form. Call get_error_details()
    only when you need the complete raw snapshot structure for programmatic processing
    (e.g., extracting all frames, all locals, or dump_path).

    Args:
        error_id: The unique error identifier (e.g., err_20260310T131600_a3f2b1).

    Returns:
        Full snapshot data or {"error": "..."} if not found.
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
    """Evaluate a Python expression against crash-point locals. Use after inspect_error()
    to test a hypothesis when the variable values alone are not conclusive
    (e.g., "type(price)", "len(items)", "items[2]['price']").

    Do NOT use this as the primary investigation method — use inspect_error() and
    dap_drill_into() first. Call evaluate_expression() only when you need to compute
    a derived value that isn't directly visible in the stored variables.

    Reconstructs the namespace from stored repr strings via ast.literal_eval,
    then runs eval(). Variables that cannot be parsed are listed in unavailable_vars
    and silently excluded from the namespace.

    Args:
        expression: Python expression to evaluate (e.g., "type(price)").
        error_id: The snapshot to evaluate against.
        frame_index: Stack frame index (0 = crash point).

    Returns:
        {success, result, error, unavailable_vars, mode}
        unavailable_vars lists variables excluded due to unparseable repr values.
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
def inspect_error(error_id: str) -> dict:
    """Primary entry point for investigating a captured Python error.

    Always call this first when asked to debug, diagnose, or explain an error.
    Returns the exception info, call stack, and crash-point variables in one call.

    Workflow:
    1. Read exception_type and exception_message to understand what went wrong.
    2. Read stack_frames to find the crash site (frame_index=0 = innermost frame).
    3. Read variables for the bad value at the crash site.
       - variablesReference == 0  → primitive value, readable directly. No further calls needed.
       - variablesReference  > 0  → nested object (dict/list/tuple). Call dap_drill_into()
         on the ONE variable most directly involved in the crash. Drill one level at a time;
         stop as soon as you can name the bad value and explain the error. Do NOT expand
         every nested variable — only the crash-relevant path.

    Args:
        error_id: The snapshot ID to investigate (from list_errors if unknown).

    Returns:
        {
          "exception_type":    str,   e.g. "TypeError"
          "exception_message": str,   e.g. "can't multiply sequence by non-int of type 'str'"
          "stack_frames": [{frame_index, function_name, file_path, line_number}, ...],
          "variables":    [{name, value, type, variablesReference}, ...]
        }
        or {"error": "..."} if the snapshot is not found.
    """
    adapter = _get_adapter(error_id)
    if adapter is None:
        return {"error": f"Snapshot not found: {error_id}"}

    store = _get_store()
    try:
        snapshot = store.get_snapshot(error_id)
        exception_type = snapshot.exception_type
        exception_message = snapshot.exception_message
    except Exception:
        exception_type = ""
        exception_message = ""

    stack_frames = [
        {
            "frame_index": frame.id,
            "function_name": frame.name,
            "file_path": frame.source_path,
            "line_number": frame.line,
        }
        for frame in adapter.session.stack_trace
    ]

    variables = adapter.session.variables.get(0)
    crash_variables = (
        [
            {
                "name": v.name,
                "value": v.value,
                "type": v.type or "",
                "variablesReference": v.variables_reference,
            }
            for v in variables
        ]
        if variables is not None
        else []
    )

    return {
        "exception_type": exception_type,
        "exception_message": exception_message,
        "stack_frames": stack_frames,
        "variables": crash_variables,
    }


@mcp.tool()
def dap_get_stack_frames(error_id: str) -> list[dict]:
    """Get call stack frames for a snapshot. Use inspect_error() instead for a
    combined stack + variables view. Call this directly only when you need frames
    for a specific non-crash frame_index before calling dap_get_variables.

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
    """Get local variables at a specific stack frame. Use inspect_error() instead
    for frame_index=0 (crash point). Call this directly only when you need variables
    at a non-crash frame (e.g., frame_index=1 for the caller context).

    Variables with variablesReference > 0 are nested objects expandable via dap_drill_into.

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
    """Expand a nested variable one level deeper. Call after inspect_error() when
    a variable's variablesReference > 0 and its value is not yet sufficient to
    explain the root cause.

    Hierarchical strategy:
      - Use the variablesReference from inspect_error()'s variables list, or from
        a prior dap_drill_into() result.
      - Expand the object most directly related to the crash site first.
      - Each returned field has its own variablesReference:
          variablesReference == 0  → primitive (string, int, None…). Stop here.
          variablesReference  > 0  → still nested. Drill further only if needed.
      - Stop as soon as you can state the bad value and explain the error.
        Do NOT expand every nested object — focus on the crash-relevant path only.

    Args:
        error_id: The snapshot to inspect.
        variables_reference: The reference integer (> 0) from inspect_error()
            or a previous dap_drill_into() call.

    Returns:
        List of {name, value, type, variablesReference} for the object's fields,
        or [] if the reference is unknown or not expandable.
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
