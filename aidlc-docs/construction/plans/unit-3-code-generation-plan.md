# Unit 3 Code Generation Plan — Hybrid DAP Server

## Unit Context
- **FR Coverage**: FR-3.1 (DAP Proxy), FR-3.2 (State Caching), FR-3.3 (Mock Mode), FR-3.4 (Success Criteria)
- **Dependencies**: Unit 1 (SnapshotStore, ErrorSnapshot), Unit 2 (tracker — no direct dep)
- **New package**: `src/errordog/dap/`
- **Modified file**: `src/errordog/__main__.py` — add `errordog dap` subcommand

## Steps

- [x] Step 1: Create `src/errordog/dap/__init__.py`
- [x] Step 2: Create `src/errordog/dap/protocol.py` — DAP Content-Length framing (read/write messages)
- [x] Step 3: Create `src/errordog/dap/session.py` — DebugSession, StackFrame, Variable domain entities
- [x] Step 4: Create `src/errordog/dap/mock.py` — MockSession: ESF snapshot → DAP responses
- [x] Step 5: Create `src/errordog/dap/proxy.py` — async TCP proxy + StoppedEvent interception + state caching
- [x] Step 6: Update `src/errordog/__main__.py` — add `errordog dap` subcommand
- [x] Step 7: Create `tests/test_dap_protocol.py` — framing read/write tests
- [x] Step 8: Create `tests/test_dap_session.py` — DebugSession state, MockSession ESF loading
- [x] Step 9: Create `tests/test_dap_mock.py` — mock DAP request/response tests
- [x] Step 10: Create `tests/test_dap_proxy.py` — proxy message routing and interception tests
- [x] Step 11: Create `aidlc-docs/construction/unit-3-hybrid-dap-server/code/code-summary.md`
