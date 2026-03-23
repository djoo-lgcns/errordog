# Business Logic Model - Unit 1: Core MCP Server & ESF

## Overview

Unit 1 implements three business logic flows:
1. Snapshot persistence (write/read from file system)
2. Error listing (summarize all stored snapshots)
3. Error detail retrieval (load full snapshot by ID)

---

## Flow 1: Save Snapshot

```
Input: ErrorSnapshot (Pydantic model)
    |
    v
Validate via Pydantic (automatic)
    |
    v
Generate error_id (if not provided)
    |  - datetime.utcnow() -> format YYYYMMDDTHHMMSS
    |  - random 6 hex chars -> os.urandom(3).hex()
    |  - combine: err_{date}T{time}_{hex}
    v
Serialize to JSON
    |  - model.model_dump()
    |  - json.dumps(data, indent=2)
    v
Write to file
    |  - path: {snapshot_dir}/{error_id}.json
    |  - ensure directory exists (mkdir -p)
    v
Return: file path
```

---

## Flow 2: List Errors (MCP Tool)

```
Input: (none)
    |
    v
Scan snapshot directory
    |  - glob("*.json")
    v
For each .json file:
    |
    +-> Try: parse JSON + validate with Pydantic
    |       |
    |       +-> Success: extract summary fields
    |       |     - error_id, timestamp, exception_type, exception_message
    |       |     - frames[0].file_path, frames[0].line_number, frames[0].function_name
    |       |
    |       +-> Failure: log warning, skip file
    |
    v
Sort summaries by timestamp descending
    |
    v
Return: list[ErrorSummary]
```

---

## Flow 3: Get Error Details (MCP Tool)

```
Input: error_id (str)
    |
    v
Construct file path
    |  - {snapshot_dir}/{error_id}.json
    v
Check file exists
    |
    +-> Not found: return error message dict
    |     {"error": "Snapshot not found", "error_id": error_id}
    |
    +-> Found: read and parse
            |
            v
        Validate with Pydantic
            |
            +-> Success: return model.model_dump()
            |
            +-> Failure: return error message dict
                  {"error": "Snapshot corrupted", "error_id": error_id}
```

---

## Flow 4: Server Startup

```
Input: CLI invocation (python -m errordog)
    |
    v
Create SnapshotStore(snapshot_dir=default)
    |  - ensure directory exists
    v
Create FastMCP server
    |  - register list_errors tool
    |  - register get_error_details tool
    v
Run server (stdio transport)
```

---

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| Snapshot directory doesn't exist | Create it automatically |
| Corrupted JSON file during list | Skip, log warning |
| Corrupted JSON file during get | Return error message dict |
| error_id not found | Return error message dict |
| Pydantic validation fails on save | Raise (programming error, should not happen) |
| File write permission denied | Raise (system error, surface to caller) |
