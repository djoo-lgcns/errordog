# Unit 3 Business Rules — Hybrid DAP Server

## Port Configuration

- BR-3.1: DAP proxy listens on `:5679` (fixed)
- BR-3.2: Proxy connects to debugpy on `localhost:5678` (fixed)
- BR-3.3: Ports are not configurable in Phase 3

---

## Session Management

- BR-3.4: Only one debug session is active at a time
- BR-3.5: While a session is active, new connection attempts are rejected with an error log
- BR-3.6: Session is cleared when the IDE disconnects

---

## Proxy Mode

- BR-3.7: All DAP messages from IDE are forwarded to debugpy unchanged
- BR-3.8: All DAP messages from debugpy are forwarded to IDE unchanged
- BR-3.9: `StoppedEvent` is intercepted and triggers state caching (non-blocking — message is still forwarded)
- BR-3.10: After intercepting `StoppedEvent`, proxy sends `stackTrace` request to debugpy and caches response
- BR-3.11: After caching stackTrace, proxy sends `variables` request per frame and caches response
- BR-3.12: Caching is done asynchronously; IDE flow is not blocked

---

## Mock Mode

- BR-3.13: Mock mode is activated when an `attach` DAP request contains an `error_id` field in its arguments
- BR-3.14: On mock attach, the ESF snapshot for `error_id` is loaded from `SnapshotStore`
- BR-3.15: If `error_id` not found, respond with DAP error response and exit mock mode
- BR-3.16: Mock session responds to `initialize`, `attach`, `threads`, `stackTrace`, `variables`, `disconnect` requests
- BR-3.17: Mock session does NOT support `continue`, `next`, `stepIn`, `stepOut`, `setBreakpoints` — respond with error
- BR-3.18: Mock session synthesizes: thread_id=1, frame ids assigned sequentially from ESF frames (index = frame_id)
- BR-3.19: Variables are read-only; `variables_reference` is always 0 (no expansion)

---

## Message Framing

- BR-3.20: DAP uses `Content-Length: N\r\n\r\n` header framing (same as LSP)
- BR-3.21: Both proxy and mock must correctly parse and emit this framing
- BR-3.22: Incomplete messages are buffered until full message is received
