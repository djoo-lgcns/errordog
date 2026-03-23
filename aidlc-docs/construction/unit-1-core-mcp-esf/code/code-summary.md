# Code Summary - Unit 1: Core MCP Server & ESF

## Created Files

### Application Code (`src/errordog/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package init with version |
| `__main__.py` | CLI entry point - creates and runs MCP server |
| `models.py` | ESF Pydantic models: Frame, ErrorSnapshot, ErrorSummary, generate_error_id() |
| `store.py` | SnapshotStore: file-based CRUD for snapshots in ~/.errordog/snapshots/ |
| `server.py` | FastMCP server with list_errors() and get_error_details() tools |

### Tests (`tests/`)

| File | Coverage |
|------|----------|
| `conftest.py` | Shared fixtures: sample_frame, sample_snapshot, snapshot_dir, populated_snapshot_dir |
| `test_models.py` | Frame validation, ErrorSnapshot validation, ErrorSummary, JSON round-trip, error_id generation |
| `test_store.py` | Save, list, get, summaries, corrupted file handling, sorting |
| `test_server.py` | MCP tools (list_errors, get_error_details), error handling, server creation |

### Configuration

| File | Purpose |
|------|---------|
| `pyproject.toml` | uv project config, Python 3.13+, dependencies (fastmcp, pydantic), pytest config |

## How to Run

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Start MCP server
uv run python -m errordog
```

## MCP Tools

- `list_errors()` - Returns summaries of all stored snapshots (sorted by timestamp desc)
- `get_error_details(error_id)` - Returns full snapshot data by ID
