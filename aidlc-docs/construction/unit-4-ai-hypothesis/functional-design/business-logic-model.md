# Unit 4 Business Logic Model — AI Hypothesis Testing

## Overview

Unit 4 adds expression evaluation and test generation capabilities via three integration points:

1. **MockAdapter DAP `evaluate` handler** — enables IDE debug console in post-mortem mode (the core post-mortem experience)
2. **MCP tool: `evaluate_expression`** — enables AI agents to evaluate expressions against snapshots or live sessions
3. **MCP tool: `generate_reproduction_test`** — generate a pytest script from a snapshot

The DAP handler and MCP tool share the same namespace reconstruction logic (ast.literal_eval → eval). MCP tools are registered on the same FastMCP instance in `server.py` (Q6: A).

`reproduce_error_in_ide` is deferred (Q5: B) — the existing `<leader>de` picker suffices.

---

## Tool 1: evaluate_expression

### Signature

```
evaluate_expression(expression: str, error_id: str, frame_index: int = 0) -> dict
```

### Flow — Mock Mode

```
1. Load snapshot from SnapshotStore by error_id
   - If not found → return {success: false, error: "Snapshot not found"}

2. Get frame at frame_index from snapshot.frames
   - If index out of range → return {success: false, error: "Frame index out of range"}

3. Reconstruct namespace:
   namespace = {}
   unavailable = []
   for name, repr_str in frame.locals.items():
       try:
           namespace[name] = ast.literal_eval(repr_str)
       except (ValueError, SyntaxError):
           unavailable.append(name)

4. Evaluate expression:
   try:
       result = eval(expression, {"__builtins__": __builtins__}, namespace)
       return {success: true, result: repr(result), unavailable_vars: unavailable, mode: "mock"}
   except Exception as e:
       return {success: false, error: f"{type(e).__name__}: {e}", unavailable_vars: unavailable, mode: "mock"}
```

### Flow — Live Mode

```
1. Check if DapServer has an active proxy session
   - If no active session → fall back to mock mode

2. Construct DAP evaluate request:
   {
     "command": "evaluate",
     "arguments": {
       "expression": expression,
       "frameId": frame_id,  // mapped from frame_index via session.stack_trace
       "context": "repl"
     }
   }

3. Send to debugpy, await response

4. Extract result from response body:
   - body.result → result string
   - body.type → type info
   return {success: true, result: body.result, mode: "live"}
```

### Mode Selection Logic

```
if active_proxy_session exists AND active_proxy_session.thread_id is not None:
    use live mode
else:
    use mock mode (load from snapshot store)
```

---

## Tool 2: generate_reproduction_test

### Signature

```
generate_reproduction_test(error_id: str) -> dict
```

### Flow

```
1. Load snapshot from SnapshotStore by error_id
   - If not found → return {error: "Snapshot not found"}

2. Select target frame:
   frame = snapshot.frames[0]  # innermost (crash point)
   if frame.function_name == "<module>" and len(snapshot.frames) > 1:
       frame = snapshot.frames[1]  # prefer named function

3. Derive module path:
   if snapshot.cwd and frame.file_path starts with snapshot.cwd:
       rel_path = relative(frame.file_path, snapshot.cwd)
       module = rel_path.replace("/", ".").removesuffix(".py")
   else:
       module = None  # will need manual import

4. Reconstruct arguments:
   args = {}
   for name, repr_str in frame.locals.items():
       try:
           args[name] = ast.literal_eval(repr_str)
       except (ValueError, SyntaxError):
           args[name] = repr_str  # use raw repr as string fallback

5. Generate test code from template:
   - import line (if module derivable)
   - function with pytest.raises
   - arg assignments as literals
   - function call

6. Write to ~/.errordog/generated_tests/test_reproduce_{error_id}.py
   - Create directory if needed

7. Return {
     error_id, test_code, file_path,
     function_name: frame.function_name,
     exception_type: snapshot.exception_type
   }
```

### Template Example

Given snapshot:
- error_id: `err_20260414T045713_5ee4d9`
- exception_type: `TypeError`
- frames[0]: `calculate_price` at `orders.py:5`, locals: `{items: [{'price': 1500, 'qty': '1'}]}`
- cwd: `/home/user/project`

Generated test:
```python
import pytest
from orders import calculate_price


def test_reproduce_err_20260414T045713_5ee4d9():
    """Auto-generated reproduction test from errordog snapshot."""
    items = [{'price': 1500, 'qty': '1'}]
    with pytest.raises(TypeError):
        calculate_price(items)
```

---

## DAP: MockAdapter `evaluate` Handler

### Purpose

Enable the IDE debug console (e.g., nvim-dap REPL) to evaluate expressions during post-mortem mock sessions. This is the developer-facing counterpart to the MCP `evaluate_expression` tool.

### DAP Protocol

The IDE sends:
```json
{
  "command": "evaluate",
  "arguments": {
    "expression": "type(items[0]['qty'])",
    "frameId": 0,
    "context": "repl"
  }
}
```

### Handler Flow

```
1. Extract expression, frameId from arguments
   - frameId maps directly to frame index (mock mode uses 0..N-1)

2. Get frame variables from session.variables[frameId]
   - If frameId not in variables → return error response

3. Reconstruct namespace (same logic as MCP tool):
   namespace = {}
   for var in frame_variables:
       parsed = _parse_repr(var.value)
       if not isinstance(parsed, str) or parsed != var.value:
           # Successfully parsed (not a raw fallback string)
           namespace[var.name] = parsed

4. Evaluate:
   try:
       result = eval(expression, {"__builtins__": __builtins__}, namespace)
       return response(body={
           "result": repr(result),
           "type": type(result).__name__,
           "variablesReference": _register(result)  # enable drill-down on result
       })
   except Exception as e:
       return response(body={
           "result": f"{type(e).__name__}: {e}",
           "type": "",
           "variablesReference": 0
       })
```

### Shared Logic

The namespace reconstruction logic is identical between:
- `MockAdapter.evaluate` (DAP handler) — uses `_parse_repr()` + `_register()` already on the class
- `evaluate_expression` (MCP tool) — uses `ast.literal_eval()`

Both use the same approach: parse repr strings → build namespace → `eval()`.

---

## Registration in server.py

Both tools are added to the existing `mcp` FastMCP instance:

```python
@mcp.tool()
def evaluate_expression(expression: str, error_id: str, frame_index: int = 0) -> dict:
    ...

@mcp.tool()
def generate_reproduction_test(error_id: str) -> dict:
    ...
```

No new entry point or server needed (Q6: A).

---

## Dependency Map

```
MockAdapter (DAP — IDE debug console)
  └── evaluate handler
        ├── _parse_repr()                     # reuse existing method
        ├── eval()                            # expression execution
        └── _register()                       # drill-down on result

server.py (MCP tools)
  ├── evaluate_expression
  │     ├── SnapshotStore.get_snapshot()      # mock mode
  │     ├── ast.literal_eval()                # namespace reconstruction
  │     ├── eval()                            # expression execution
  │     └── DapServer active session          # live mode (optional)
  │           └── DAP evaluate request → debugpy
  │
  └── generate_reproduction_test
        ├── SnapshotStore.get_snapshot()
        ├── ast.literal_eval()                # arg reconstruction
        ├── template rendering                # string formatting
        └── file write to ~/.errordog/generated_tests/
```
