# Code Generation Plan - Unit 1: Core MCP Server & ESF

## Unit Context
- **Unit**: Unit 1 - Core MCP Server & ESF
- **Requirements**: FR-1.1 (ESF schema), FR-1.2 (MCP server scaffolding), FR-1.3 (MCP tools), FR-1.4 (success criteria)
- **Dependencies**: None (foundation unit)
- **Workspace Root**: /Users/djoo/Projects/debugger-v4
- **Code Location**: /Users/djoo/Projects/debugger-v4/src/errordog/

---

## Generation Steps

### Step 1: Project Structure Setup
- [x] Create `pyproject.toml` with uv project config (Python 3.13+, dependencies: fastmcp, pydantic)
- [x] Create `src/errordog/__init__.py`
- [x] Create `src/errordog/__main__.py` (CLI entry point)
- [x] Create `tests/` directory with `__init__.py` and `conftest.py`

### Step 2: ESF Domain Models (FR-1.1)
- [x] Create `src/errordog/models.py`
  - `Frame` Pydantic model (file_path, line_number, function_name, locals)
  - `ErrorSnapshot` Pydantic model (error_id, timestamp, exception_type, exception_message, frames)
  - `ErrorSummary` Pydantic model (summary fields + top frame info)
  - `generate_error_id()` helper function (timestamp-based: `err_{YYYYMMDD}T{HHMMSS}_{6hex}`)

### Step 3: ESF Models Unit Tests
- [x] Create `tests/test_models.py`
  - Test Frame validation (valid and invalid data)
  - Test ErrorSnapshot validation (valid and invalid data)
  - Test ErrorSummary construction
  - Test error_id generation format
  - Test JSON serialization round-trip

### Step 4: Snapshot Store (FR-1.2)
- [x] Create `src/errordog/store.py`
  - `SnapshotStore` class with configurable snapshot_dir
  - `ensure_directory()` - create dir if missing
  - `list_snapshots()` - scan dir, parse JSON, return error_id list
  - `get_snapshot(error_id)` - load single snapshot by ID
  - `save_snapshot(snapshot)` - write snapshot to JSON file
  - `list_summaries()` - return list of ErrorSummary (for list_errors tool)
  - Corrupted file handling: skip with warning log

### Step 5: Snapshot Store Unit Tests
- [x] Create `tests/test_store.py`
  - Test ensure_directory creates dir
  - Test save_snapshot writes valid JSON
  - Test list_snapshots returns stored IDs
  - Test get_snapshot returns correct data
  - Test list_summaries returns summaries with top frame info
  - Test corrupted file is skipped silently
  - Test missing error_id returns appropriate error
  - Use tmp_path fixture for isolated test directories

### Step 6: MCP Server & Tools (FR-1.2, FR-1.3)
- [x] Create `src/errordog/server.py`
  - `create_server()` function returning configured FastMCP instance
  - `list_errors()` MCP tool - delegates to store.list_summaries()
  - `get_error_details(error_id)` MCP tool - delegates to store.get_snapshot()
  - Error handling: return descriptive error dicts (not exceptions)

### Step 7: MCP Server Unit Tests
- [x] Create `tests/test_server.py`
  - Test list_errors returns summaries
  - Test get_error_details returns full snapshot
  - Test get_error_details with invalid ID returns error dict
  - Test server creation and tool registration

### Step 8: CLI Entry Point (FR-1.2)
- [x] Implement `src/errordog/__main__.py`
  - `main()` function: create server, run with stdio transport
  - Wire up SnapshotStore with default directory

### Step 9: Documentation Summary
- [x] Create `aidlc-docs/construction/unit-1-core-mcp-esf/code/code-summary.md`
  - List all created files with brief descriptions
  - Note test coverage areas
  - Document how to run the server

---

## File Manifest

| Step | File | Type |
|------|------|------|
| 1 | `pyproject.toml` | Config |
| 1 | `src/errordog/__init__.py` | Package init |
| 1 | `src/errordog/__main__.py` | Entry point |
| 1 | `tests/__init__.py` | Test package |
| 1 | `tests/conftest.py` | Test fixtures |
| 2 | `src/errordog/models.py` | Business logic |
| 3 | `tests/test_models.py` | Unit tests |
| 4 | `src/errordog/store.py` | Business logic |
| 5 | `tests/test_store.py` | Unit tests |
| 6 | `src/errordog/server.py` | MCP server |
| 7 | `tests/test_server.py` | Unit tests |
| 8 | `src/errordog/__main__.py` | CLI (update) |
| 9 | `aidlc-docs/.../code-summary.md` | Documentation |
