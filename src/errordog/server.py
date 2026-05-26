"""Errordog MCP server — post-mortem DAP inspection tools."""

from pathlib import Path

from fastmcp import FastMCP

from errordog.dap.mock import MockAdapter
from errordog.store import SnapshotStore

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
    """List captured Python error snapshots. Call this when no error_id is known.

    Returns snapshots sorted by timestamp descending (most recent first).
    Each entry includes: error_id, timestamp, exception_type, exception_message,
    file_path, line_number, function_name.

    After getting an error_id, call dap_get_stack_frames(error_id) to investigate.
    """
    store = _get_store()
    summaries = store.list_summaries()
    return [s.model_dump() for s in summaries]


@mcp.tool()
def dap_get_stack_frames(error_id: str) -> list[dict]:
    """Get call stack for a captured Python error. Call this first.

    Returns frames ordered innermost-first: frame_index=0 is the crash point.
    Use frame_index values in dap_get_variables to read locals at each frame.

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
    """Get local variables at a stack frame. Call after dap_get_stack_frames.

    Each variable has a "value" field with the full Python repr — read it first.
    This is often sufficient to identify the root cause without further calls.

    Only call dap_drill_into if the "value" repr is too large or truncated to
    identify the specific bad value (e.g. a long list where the offending element
    is not obvious). Do NOT drill just because variablesReference > 0.

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
    """Expand a nested variable one level deeper. Call only when needed.

    Call this only when dap_get_variables' "value" field is insufficient:
      - repr is truncated or too long to spot the bad value
      - a list where you cannot tell which element is wrong from the repr alone
    Do NOT drill a dict just because variablesReference > 0 — if the repr shows
    all key-value pairs, you can already read it directly.

    Drill into the ONE most suspicious variable. Stop as soon as you can name
    the bad value. Do NOT expand every object with variablesReference > 0.

    Args:
        error_id: The snapshot to inspect.
        variables_reference: The reference integer (> 0) from dap_get_variables
            or a previous dap_drill_into call.

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
