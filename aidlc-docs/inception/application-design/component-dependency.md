# Component Dependencies - Phase 1: Core MCP Server & ESF

## Dependency Matrix

| Component       | Depends On          | Depended On By       |
|-----------------|---------------------|----------------------|
| models.py       | (none - leaf)       | store.py, server.py  |
| store.py        | models.py           | server.py            |
| server.py       | store.py, models.py | __main__.py          |
| __main__.py     | server.py           | (none - entry point) |

## Dependency Graph

```
__main__.py
    |
    v
server.py
    |
    v
store.py
    |
    v
models.py
```

## Communication Patterns

All communication in Phase 1 is **in-process function calls**:

- `__main__.py` calls `create_server()` from `server.py`
- MCP tool handlers in `server.py` call `SnapshotStore` methods from `store.py`
- `store.py` uses `ErrorSnapshot` / `Frame` models from `models.py` for validation and serialization
- `store.py` reads/writes JSON files to the file system

## External Dependencies

| Dependency | Used By    | Purpose                          |
|------------|------------|----------------------------------|
| fastmcp    | server.py  | MCP protocol server              |
| pydantic   | models.py  | ESF schema validation            |
| (stdlib)   | store.py   | pathlib, json for file I/O       |

## Data Flow

```
[AI Agent / Claude Code]
        |
        | MCP Protocol (stdio)
        v
    server.py
        |
        | function call
        v
    store.py
        |
        | file I/O (read JSON)
        v
  ~/.errordog/snapshots/*.json
```
