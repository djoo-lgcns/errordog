# Services - Phase 1: Core MCP Server & ESF

> Phase 1 has a simple architecture with no service orchestration layer. The MCP server directly delegates to the Snapshot Store.

## Service Architecture

Phase 1 does not require a separate service layer. The interaction is straightforward:

```
MCP Tool Request --> server.py --> store.py --> File System
                                      |
                                      v
                                  models.py (validation)
```

### Rationale for No Service Layer

- Only 2 MCP tools (`list_errors`, `get_error_details`)
- No complex orchestration or cross-component coordination
- Direct delegation from MCP tools to SnapshotStore is sufficient
- A service layer would be over-engineering at this stage

### Future Phases

Service orchestration will be introduced when needed:
- **Phase 2**: Tracker writes snapshots (extends store, no orchestration needed)
- **Phase 3**: DAP proxy may require a coordination service between MCP and DAP
- **Phase 4**: AI tools will require orchestration across DAP, store, and evaluation
