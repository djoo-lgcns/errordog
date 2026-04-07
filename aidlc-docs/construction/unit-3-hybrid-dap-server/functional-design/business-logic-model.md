# Unit 3 Business Logic Model — Hybrid DAP Server

## Module Structure

```
src/errordog/dap/
├── __init__.py
├── protocol.py     # DAP message framing & parsing
├── session.py      # DebugSession state container
├── proxy.py        # Proxy mode: bidirectional forwarding + interception
└── mock.py         # Mock mode: ESF-backed DAP responder
```

CLI entry via `__main__.py`:
```
errordog dap   →  starts DAP server (proxy or mock based on first connect)
```

---

## Startup Flow

```
errordog dap
  └─ start TCP server on :5679
       └─ wait for IDE connection
            ├─ [attach with error_id] → MockSession(error_id)
            └─ [attach without error_id / launch] → ProxySession → connect to :5678
```

---

## Proxy Mode Flow

```
IDE ──request──► proxy ──forward──► debugpy
IDE ◄─response── proxy ◄─forward─── debugpy

StoppedEvent received from debugpy:
  1. Forward to IDE immediately
  2. Async: send stackTrace request to debugpy
  3. Async: for each frame, send variables request to debugpy
  4. Cache all responses in DebugSession
```

---

## Mock Mode Flow

```
IDE ──attach(error_id)──► MockSession
  └─ load ESF snapshot from SnapshotStore
  └─ build synthetic DebugSession:
       stack_trace ← snapshot.frames
       variables   ← frame.locals per frame

IDE ──threads──► MockSession ──► [{"id": 1, "name": "MainThread"}]
IDE ──stackTrace(threadId=1)──► MockSession ──► frames from ESF
IDE ──variables(frameId=N)──►  MockSession ──► locals from ESF frame[N]
IDE ──disconnect──► MockSession ──► terminate
```

---

## DAP Message Framing (protocol.py)

```
read_message(reader) → dict:
  read until b'\r\n\r\n'
  parse Content-Length header
  read exactly N bytes
  return json.loads(body)

write_message(writer, msg: dict) → None:
  body = json.dumps(msg).encode()
  writer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
```

---

## State Caching Logic (proxy.py)

```
on_event(event: DapMessage):
  if event.event == "stopped":
    session.thread_id = event.body["threadId"]
    asyncio.create_task(cache_state(session.thread_id))

async cache_state(thread_id):
  st_response = await send_to_debugpy(stackTrace, threadId=thread_id)
  session.stack_trace = parse_stack_frames(st_response)
  session.frame_id = session.stack_trace[0].id

  for frame in session.stack_trace:
    var_response = await send_to_debugpy(variables, frameId=frame.id)
    session.variables[frame.id] = parse_variables(var_response)
```

---

## ESF → DAP Mapping (mock.py)

| ESF Field | DAP Response Field |
|-----------|-------------------|
| `frame.function_name` | `stackFrame.name` |
| `frame.file_path` | `stackFrame.source.path` |
| `frame.line_number` | `stackFrame.line` |
| `frame index` | `stackFrame.id` (0-based) |
| `frame.locals[key]` | `variable.name` |
| `frame.locals[value]` | `variable.value` |
| (type inferred from repr) | `variable.type` |
