# Unit 3 Code Summary — Hybrid DAP Server

## Created Files

### Application Code
| File | Description |
|------|-------------|
| `src/errordog/dap/__init__.py` | Package initializer |
| `src/errordog/dap/protocol.py` | DAP Content-Length framing (read_message, write_message, encode_message) |
| `src/errordog/dap/session.py` | Domain entities: DebugSession, StackFrame, Variable |
| `src/errordog/dap/mock.py` | MockAdapter: ESF snapshot → DAP responses |
| `src/errordog/dap/proxy.py` | DapServer: async TCP proxy + StoppedEvent state caching |

### Modified Files
| File | Change |
|------|--------|
| `src/errordog/__main__.py` | Added `errordog dap` subcommand routing to `proxy.run()` |

### Tests
| File | Tests |
|------|-------|
| `tests/test_dap_protocol.py` | 8 tests — framing encode/decode, EOF, missing header |
| `tests/test_dap_session.py` | 7 tests — StackFrame, Variable, DebugSession defaults |
| `tests/test_dap_mock.py` | 12 tests — initialize, attach, threads, stackTrace, scopes, variables, disconnect, unsupported |
| `tests/test_dap_proxy.py` | 8 tests — _intercept state caching, session guard |

## Test Results
- **Unit 3**: 35/35 tests passing
- **Total**: 94/94 tests passing

## CLI Usage
```bash
errordog dap        # start DAP proxy on :5679
```

## Mode Selection
- IDE sends `attach` with `error_id` in arguments → **mock mode** (ESF snapshot)
- IDE sends `attach` without `error_id` → **proxy mode** (forward to debugpy :5678)
