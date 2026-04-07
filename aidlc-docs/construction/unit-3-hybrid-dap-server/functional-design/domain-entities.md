# Unit 3 Domain Entities — Hybrid DAP Server

## DapMessage

A single DAP protocol message (JSON-RPC style).

| Field | Type | Description |
|-------|------|-------------|
| `seq` | `int` | Sequence number |
| `type` | `str` | `"request"`, `"response"`, `"event"` |
| `command` | `str \| None` | Command name (requests/responses) |
| `event` | `str \| None` | Event name (events) |
| `body` | `dict \| None` | Message payload |
| `request_seq` | `int \| None` | For responses: seq of the request |
| `success` | `bool \| None` | For responses: success flag |

---

## DebugSession

Holds live proxy session state. Populated as DAP messages flow through.

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | `int \| None` | Active thread from last StoppedEvent |
| `frame_id` | `int \| None` | Top frame id from last stackTrace response |
| `stack_trace` | `list[StackFrame]` | All frames from last stackTrace response |
| `variables` | `dict[int, list[Variable]]` | frameId → variables from variables responses |
| `mode` | `str` | `"proxy"` or `"mock"` |
| `error_id` | `str \| None` | Set in mock mode |

---

## StackFrame

One frame entry from DAP `stackTrace` response.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Frame id (referenced in variables requests) |
| `name` | `str` | Function name |
| `source_path` | `str \| None` | File path |
| `line` | `int` | Line number |

---

## Variable

One variable entry from DAP `variables` response.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Variable name |
| `value` | `str` | String repr of value |
| `type` | `str \| None` | Python type name |
| `variables_reference` | `int` | 0 if leaf, >0 if expandable |

---

## MockSession (extends DebugSession)

Pre-populated from an ESF snapshot. No live debugpy connection.

Loaded from `ErrorSnapshot`:
- `stack_trace` ← `snapshot.frames` (converted to `StackFrame`)
- `variables` ← `frame.locals` per frame (converted to `Variable`)
- `thread_id` = 1 (synthetic)
- `frame_id` = 0 (top frame)
