"""Errordog MCP server with tools for error snapshot management."""

from pathlib import Path

from fastmcp import FastMCP

from errordog.store import SnapshotStore

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


def create_server(snapshot_dir: Path | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance with tools registered."""
    global _store
    _store = SnapshotStore(snapshot_dir=snapshot_dir)
    return mcp
