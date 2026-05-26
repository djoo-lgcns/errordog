# Errordog — Debugging Workflow for AI Agents

Errordog captures Python runtime errors as snapshots and exposes them via MCP tools.
When asked to investigate an error, diagnose a crash, or debug a Python issue,
use the Errordog MCP tools in the following sequence.

## Standard Investigation Sequence

```
list_errors                          # only if error_id is unknown
  └─ dap_get_stack_frames(error_id)  # always start here
       └─ dap_get_variables(error_id, frame_index=0)
            └─ dap_drill_into(error_id, variablesReference)  # if needed
```

### Step-by-step

1. **If no error_id given** → call `list_errors` to find the most recent snapshot.

2. **dap_get_stack_frames(error_id)**
   Inspect the call stack. Identify the innermost frame (frame_index=0) as the
   crash site. Note the function name and the line where the exception was raised.

3. **dap_get_variables(error_id, frame_index=0)**
   Get local variables at the crash point. Look for the variable directly involved
   in the failing expression (e.g., a None value, a wrong type, a missing key).
   Variables with `variablesReference > 0` are nested objects that can be expanded.

4. **dap_drill_into(error_id, variablesReference)** — hierarchical, early-stop
   Expand only the nested object most directly related to the crash:
   - Start with the variable closest to the error site.
   - Drill one level at a time.
   - Stop as soon as you have a specific value (e.g., `price='free'`, `role` key missing)
     that fully explains the crash.
   - Do **not** expand every object with variablesReference > 0 indiscriminately.

## What to Report

After investigation, state in 2–3 sentences:
- The exact variable and value that caused the error (with concrete evidence from the tools)
- The function and line number where it crashed
- The fix or the condition that needs to be guarded

## Available Tools

| Tool | Purpose |
|------|---------|
| `list_errors` | List all captured snapshots (most recent first) |
| `get_error_details` | Full snapshot JSON for a given error_id |
| `evaluate_expression` | Eval a Python expression against frame locals |
| `generate_reproduction_test` | Generate a pytest reproducer for the crash |
| `dap_get_stack_frames` | Get call stack (Step 1) |
| `dap_get_variables` | Get locals at a frame (Step 2) |
| `dap_drill_into` | Expand a nested object (Step 3, hierarchical) |
