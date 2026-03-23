# Application Design - Phase 1: Core MCP Server & ESF

> Consolidated design document. See individual files for details.

## Architecture Summary

Errordog Phase 1 is a **single Python package** (`errordog`) with 4 flat modules providing a FastMCP server that manages ESF error snapshots.

```
+-----------------------------------------------------------+
|                     errordog (package)                     |
|                                                           |
|  +-------------+  +--------------+  +-----------------+  |
|  |  models.py  |  |  store.py    |  |  server.py      |  |
|  |  (ESF       |  |  (Snapshot   |  |  (MCP Server    |  |
|  |   Schema)   |  |   Storage)   |  |   & Tools)      |  |
|  +-------------+  +--------------+  +-----------------+  |
|                                                           |
|  +-------------+                                          |
|  | __main__.py |                                          |
|  | (CLI Entry) |                                          |
|  +-------------+                                          |
+-----------------------------------------------------------+
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package structure | Single package, flat modules | Simple for Phase 1, extendable later |
| ESF validation | Pydantic models | Runtime validation, easy JSON serialization |
| Server startup | CLI entry point (`python -m errordog`) | Standard Python pattern |
| Service layer | None (direct delegation) | Only 2 MCP tools, no orchestration needed |
| Storage | File-based JSON (`~/.errordog/snapshots/`) | Simple, portable, no DB dependency |

## Components

| ID | Module | Purpose |
|----|--------|---------|
| C1 | `errordog/models.py` | ESF Pydantic models (ErrorSnapshot, Frame) |
| C2 | `errordog/store.py` | File-based snapshot storage (SnapshotStore) |
| C3 | `errordog/server.py` | FastMCP server with `list_errors` and `get_error_details` tools |
| C4 | `errordog/__main__.py` | CLI entry point |

## Key Interfaces

### MCP Tools (exposed to AI agents)
- `list_errors()` -> list of snapshot summaries
- `get_error_details(error_id: str)` -> full ESF JSON

### Internal
- `SnapshotStore.list_snapshots()` -> list of error_id strings
- `SnapshotStore.get_snapshot(error_id)` -> ErrorSnapshot model
- `SnapshotStore.save_snapshot(snapshot)` -> saved file path

## Dependencies

```
__main__.py --> server.py --> store.py --> models.py
```

External: `fastmcp`, `pydantic`

## Data Flow

```
[AI Agent] --MCP(stdio)--> server.py --call--> store.py --read--> ~/.errordog/snapshots/*.json
```

## Detailed Artifacts
- [components.md](components.md) - Component definitions and responsibilities
- [component-methods.md](component-methods.md) - Method signatures
- [services.md](services.md) - Service layer rationale
- [component-dependency.md](component-dependency.md) - Dependencies and data flow
