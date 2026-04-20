# Unit 4 Functional Design Plan — AI Hypothesis Testing & Auto-Test Generation

## Plan Overview

Unit 4 adds three MCP tools that enable AI agents (and developers) to analyze error snapshots more deeply:

1. **`evaluate_expression(expression, frame_id, error_id)`** — execute a Python expression against the captured locals of a specific stack frame
2. **`generate_reproduction_test(error_id)`** — generate a pytest script that reproduces the error
3. **`reproduce_error_in_ide(error_id)`** — trigger Neovim to attach to the snapshot via RPC

## Execution Steps

- [ ] Step 1: Analyze context — review existing models, store, server, DAP mock, tracker
- [ ] Step 2: Collect design answers from user
- [ ] Step 3: Design domain entities for Unit 4
- [ ] Step 4: Design business rules for Unit 4
- [ ] Step 5: Design business logic model for Unit 4
- [ ] Step 6: Write functional design artifacts
- [ ] Step 7: Present for approval

---

## Design Questions

### Q1 — `evaluate_expression` scope

The requirement says "Execute Python expression in stopped state (live or mock)."

For **mock mode**, we have the stored locals as repr strings. We can reconstruct a namespace via `ast.literal_eval` and then `eval()` the expression against it (only literal-safe values would be available).

For **live (proxy) mode**, we would need to forward a DAP `evaluate` request to the running debugpy instance.

**Which modes should `evaluate_expression` support?**

A) Mock only (eval against reconstructed snapshot locals) — simplest, self-contained
B) Both mock and live — mock uses snapshot, live forwards to debugpy via DAP
C) Mock only for now, live as a future enhancement

[Answer]:

---

### Q2 — `evaluate_expression` safety

`eval()` can execute arbitrary Python code. For a developer tool, this is expected behavior (like a REPL), but it does carry risk.

**What level of sandboxing?**

A) No sandboxing — trust the developer (same as Python REPL / debugger console)
B) Restrict to read-only operations — block assignments, imports, side effects
C) Use `ast.literal_eval` only — only evaluate literal expressions (very limited)

[Answer]:

---

### Q3 — `generate_reproduction_test` strategy

The requirement says "generate pytest script that reproduces the crash with mocked entry-point parameters."

Given a snapshot with frames like:
```
calculate_price(orders) at orders.py:5  →  locals: {items: [{...}, ...]}
<module> at orders.py:14               →  locals: {orders: [...]}
```

**How should the test be generated?**

A) Template-based — fill in function name, arguments from top frame locals, assert raises the same exception type
B) LLM-assisted — send snapshot to the connected AI agent and let it generate the test (MCP tool returns the snapshot data formatted for LLM consumption, not the test itself)
C) Template as default, with an option for LLM-assisted refinement

[Answer]:

---

### Q4 — `generate_reproduction_test` output

**Where should the generated test be written?**

A) Return as a string via the MCP tool response (AI agent/developer decides where to save)
B) Write to `tests/` directory in the project automatically
C) Write to a staging location like `~/.errordog/generated_tests/`

[Answer]:

---

### Q5 — `reproduce_error_in_ide` mechanism

The requirement says "Send Neovim RPC command to auto-attach to Errordog Mock mode."

This requires:
- Knowing the Neovim socket path (e.g., `$NVIM_LISTEN_ADDRESS` or discovered from `/tmp/`)
- Sending an RPC command equivalent to running `dap.run({type='errordog', request='attach', error_id='...'})` in Neovim

**Is Neovim RPC integration essential for the prototype?**

A) Yes — implement it, this is a key differentiator
B) No — skip for now, `<leader>de` picker is sufficient. Focus on the other two tools.
C) Implement discovery only — detect running Neovim instances and their sockets, but don't send RPC commands yet

[Answer]:

---

### Q6 — MCP tool registration

**Should the Phase 4 tools be registered on the same MCP server instance (`errordog serve`)?**

A) Yes — same server, same `server.py` (add tools alongside `list_errors` and `get_error_details`)
B) Separate module — new `tools/` package, but still registered on the same FastMCP instance
C) Separate server — new entry point for AI tools

[Answer]:

---

### Q7 — Expression evaluation context

When evaluating an expression against a frame, we have `frame.locals` as `dict[str, str]` (repr strings).

For example: `items` = `"[{'price': 1500, 'qty': 2}, {'price': 3000, 'qty': '1'}]"`

We can reconstruct this via `ast.literal_eval`. But some values won't parse (custom classes, file handles, etc.).

**How should unparseable values be handled?**

A) Skip them — only inject parseable values into the eval namespace
B) Inject as raw strings — `items = "[{'price': 1500, ...}]"` (string, not list)
C) Skip and report which variables were unavailable

[Answer]:
