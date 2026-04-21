# Unit 4 Domain Entities — AI Hypothesis Testing

## New Entities

### EvalRequest

Input for the `evaluate_expression` MCP tool.

| Field | Type | Description |
|-------|------|-------------|
| expression | str | Python expression to evaluate |
| error_id | str | Snapshot to evaluate against |
| frame_index | int | Stack frame index (0 = crash point, default 0) |

### EvalResult

Output from `evaluate_expression`.

| Field | Type | Description |
|-------|------|-------------|
| expression | str | The expression that was evaluated |
| result | str | repr() of the evaluation result |
| success | bool | Whether evaluation succeeded |
| error | str or None | Error message if evaluation failed |
| unavailable_vars | list[str] | Variables skipped (unparseable repr) |
| mode | str | "mock" or "live" |

### TestGenerationRequest

Input for the `generate_reproduction_test` MCP tool.

| Field | Type | Description |
|-------|------|-------------|
| error_id | str | Snapshot to generate test from |

### TestGenerationResult

Output from `generate_reproduction_test`.

| Field | Type | Description |
|-------|------|-------------|
| error_id | str | Source snapshot |
| test_code | str | Generated pytest source code |
| file_path | str | Where the test was written |
| function_name | str | The function under test |
| exception_type | str | Expected exception |

## Existing Entities (Referenced)

### ErrorSnapshot (from models.py)

Used as the data source for both tools. Fields: error_id, timestamp, exception_type, exception_message, frames[], cwd.

### Frame (from models.py)

Individual stack frame. Fields: file_path, line_number, function_name, locals (dict[str, str] — repr strings).

### DebugSession (from session.py)

Mutable state for proxy mode. Used by `evaluate_expression` in live mode to forward DAP evaluate requests.

## Entity Relationships

```
ErrorSnapshot 1──* Frame
     |
     v
EvalRequest ──> ErrorSnapshot (lookup by error_id)
     |
     v
EvalResult (computed from frame locals + expression)

TestGenerationRequest ──> ErrorSnapshot (lookup by error_id)
     |
     v
TestGenerationResult (generated from top frame + exception info)
```
