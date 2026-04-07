# Unit 3 Test Instructions — Hybrid DAP Server

## Unit Tests

```bash
uv run pytest tests/test_dap_protocol.py tests/test_dap_session.py \
               tests/test_dap_mock.py tests/test_dap_proxy.py -v
```

Expected: **35/35 passed**

| File | Tests | Coverage |
|------|-------|----------|
| `test_dap_protocol.py` | 8 | Content-Length framing, EOF, bad header |
| `test_dap_session.py` | 7 | StackFrame, Variable, DebugSession |
| `test_dap_mock.py` | 12 | initialize, attach, threads, stackTrace, scopes, variables, disconnect, unsupported |
| `test_dap_proxy.py` | 8 | _intercept caching, session guard |

---

## Integration Test — Mock Mode (ESF → IDE)

Tests that an ESF snapshot can be visualized through a real DAP client.

### Prerequisites
- At least one snapshot in `~/.errordog/snapshots/` (run `uv run python demo.py` to generate one)
- A DAP client (e.g., `nvim-dap`, VS Code, or the test script below)

### 1. Get a snapshot error_id
```bash
uv run python scripts/test_tools_manual.py
# Copy the error_id from the top entry in list_errors() output
```

### 2. Start the DAP server
```bash
errordog dap
# Listening on localhost:5679
```

### 3. Attach from IDE (Neovim nvim-dap config)
```lua
-- .nvim/dap.lua
dap.configurations.python = {
  {
    type = "errordog-mock",
    request = "attach",
    name = "Errordog: inspect snapshot",
    connect = { host = "localhost", port = 5679 },
    error_id = "<paste-error-id-here>",
  }
}
```

### Expected behavior
1. IDE shows "stopped at exception" in the file where the error occurred
2. Stack trace shows all captured frames
3. Variables panel shows local variables at each frame
4. Disconnect closes the session cleanly

---

## Integration Test — Proxy Mode (IDE → debugpy)

Tests that the proxy transparently forwards a real debugpy session.

### 1. Start target process with debugpy
```bash
python -m debugpy --listen 5678 --wait-for-client demo.py
```

### 2. Start the errordog DAP proxy
```bash
errordog dap
# Listening on localhost:5679
```

### 3. Attach IDE to proxy (not directly to debugpy)
```json
// VS Code launch.json
{
  "type": "python",
  "request": "attach",
  "name": "Errordog proxy",
  "connect": { "host": "localhost", "port": 5679 }
}
```

### Expected behavior
1. Breakpoints work normally (set in IDE, hit in process)
2. Stack trace, variables visible at breakpoints
3. Step/continue/stop all work
4. After hitting a breakpoint, `DebugSession` caches threadId, stackTrace, variables internally
