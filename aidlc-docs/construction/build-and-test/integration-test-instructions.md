# Integration Test Instructions - Unit 1

## Purpose
Test the complete flow from MCP tool invocation through store to file system.

## Test Scenarios

### Scenario 1: End-to-End Snapshot Lifecycle
- **Description**: Save a snapshot via store, then retrieve it via MCP tools
- **Setup**: Temporary snapshot directory
- **Test Steps**:
  1. Create SnapshotStore with temp directory
  2. Create server with that store
  3. Save a sample ErrorSnapshot via store
  4. Call `list_errors()` and verify snapshot appears in results
  5. Call `get_error_details(error_id)` and verify full data returned
- **Expected Results**: Snapshot saved, listed, and retrieved correctly

### Scenario 2: MCP Protocol Integration (Manual)
- **Description**: Verify MCP server responds to real MCP client requests
- **Setup**:
  1. Create dummy snapshot files in `~/.errordog/snapshots/`
  2. Start server: `uv run python -m errordog`
- **Test Steps**:
  1. Connect with an MCP client (e.g., Claude Code with errordog configured)
  2. Call `list_errors` tool
  3. Call `get_error_details` with a known error_id
- **Expected Results**: Both tools return valid JSON responses

## Notes
- Unit 1 is a single-unit delivery; cross-unit integration tests will be added in Phase 2+
- MCP protocol integration testing requires an MCP client (manual or automated)
