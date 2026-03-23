# Components - Phase 1: Core MCP Server & ESF

> Later phases will extend this document as new components are introduced.

## Component Overview

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

## C1: ESF Models (`errordog/models.py`)

- **Purpose**: Define the Errordog Snapshot Format (ESF) as Pydantic models
- **Responsibilities**:
  - Define `Frame` model (file_path, line_number, function_name, locals, globals)
  - Define `ErrorSnapshot` model (error_id, timestamp, exception_type, exception_message, frames)
  - Provide JSON serialization/deserialization
  - Validate snapshot data at runtime

## C2: Snapshot Store (`errordog/store.py`)

- **Purpose**: Manage file-based persistence of ESF snapshots
- **Responsibilities**:
  - Manage snapshot directory (`~/.errordog/snapshots/`)
  - List available snapshot files
  - Read and parse snapshot files into Pydantic models
  - Write snapshot data to files
  - Ensure directory existence on startup

## C3: MCP Server (`errordog/server.py`)

- **Purpose**: Expose snapshot data to AI agents via MCP protocol
- **Responsibilities**:
  - Initialize FastMCP server instance
  - Register MCP tools (`list_errors`, `get_error_details`)
  - Delegate data operations to Snapshot Store
  - Handle MCP protocol lifecycle

## C4: CLI Entry Point (`errordog/__main__.py`)

- **Purpose**: Provide CLI interface to start the Errordog server
- **Responsibilities**:
  - Parse CLI arguments (if any)
  - Initialize and start MCP server
  - Support `python -m errordog` invocation
