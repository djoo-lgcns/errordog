# Errordog — Debugging Workflow for AI Agents

Errordog captures Python runtime errors as snapshots and exposes them via MCP tools.
When asked to investigate an error, diagnose a crash, or debug a Python issue,
use the Errordog MCP tools in the following sequence.

## Standard Investigation Sequence

```
dap_get_stack_frames(error_id)          # Step 1: locate the crash frame
  └─ dap_get_variables(error_id, 0)     # Step 2: read locals at crash point
       └─ dap_drill_into(error_id, ref) # Step 3: expand nested value (if needed)
```

### Step-by-step

1. **dap_get_stack_frames(error_id)**
   Inspect the call stack. Identify the crash site: `frame_index=0` is the innermost
   (crash) frame. Note the function name and the line where the exception was raised.

2. **dap_get_variables(error_id, frame_index=0)**
   Get local variables at the crash point. Each variable has a **"value"** field
   containing its full Python repr — **read this first**.
   - If the bad value is directly readable from "value", state the root cause
     immediately. **Do NOT call dap_drill_into.**
   - `variablesReference > 0` means structured expansion is available, but does NOT
     mean the value is hidden. The repr in "value" is always complete.

3. **dap_drill_into(error_id, variablesReference)** — conditional, early-stop
   Only call when the "value" repr is insufficient to identify the specific bad value:
   - A long list where the offending element is not obvious from the repr alone.
   - A repr that appears truncated (ends with `...`).
   - Do **NOT** drill a dict just to confirm a missing key — if the repr shows all
     key-value pairs, you can already read it directly.
   - Drill into the ONE most suspicious variable, one level at a time.
   - **Stop** as soon as you can name the bad value (e.g., `price='free'`, key absent).

## What to Report

After investigation, state in 2–3 sentences:
- The exact variable and value that caused the error (with concrete evidence from the tools)
- The function and line number where it crashed
- The fix or the condition that needs to be guarded

## Available Tools

| Tool | Purpose |
|------|---------|
| `dap_get_stack_frames` | Get call stack — Step 1 |
| `dap_get_variables` | Get locals at a frame — Step 2 |
| `dap_drill_into` | Expand a nested object — Step 3 (conditional) |
