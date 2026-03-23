# Business Logic Model - Unit 2: Python Runtime Tracker

## Overview

Unit 2 implements one main flow triggered automatically on uncaught exceptions.

---

## Flow 1: Exception Capture (sys.excepthook)

```
Uncaught exception occurs
    |
    v
sys.excepthook(exc_type, exc_value, exc_tb) called
    |
    v
Guard: skip if KeyboardInterrupt or SystemExit
    |
    v
Try: capture snapshot
    |
    +-> Extract exception info
    |     - exception_type = exc_type.__name__
    |     - exception_message = str(exc_value)
    |
    +-> Walk traceback frames
    |     - tb = exc_tb
    |     - while tb is not None (up to MAX_FRAMES):
    |         - frame = tb.tb_frame
    |         - extract file_path, line_number, function_name
    |         - serialize f_locals (repr + truncate)
    |         - tb = tb.tb_next
    |     - reverse frames (innermost first)
    |
    +-> Build ErrorSnapshot
    |     - error_id = generate_error_id()
    |     - timestamp = datetime.now(UTC).isoformat()
    |     - frames, exception_type, exception_message
    |
    +-> Save via SnapshotStore
    |     - store.save_snapshot(snapshot)
    |
    v
Except: log warning if anything fails
    |
    v
Call original excepthook(exc_type, exc_value, exc_tb)
```

---

## Flow 2: Module Import (Auto-Activation)

```
import errordog.tracker
    |
    v
Module-level code executes:
    |
    +-> Check if already installed (guard flag)
    |
    +-> Store _original_excepthook = sys.excepthook
    |
    +-> sys.excepthook = _errordog_excepthook
    |
    +-> Set _installed = True
    |
    v
Done (hook is active)
```

---

## Helper: Safe Variable Serialization

```
Input: f_locals (dict)
    |
    v
For each (name, value) in f_locals.items():
    |
    +-> Try: repr_str = repr(value)
    |   Except: repr_str = "<unrepresentable: {type}>"
    |
    +-> If len(repr_str) > MAX_REPR_LENGTH:
    |       repr_str = repr_str[:MAX_REPR_LENGTH] + "..."
    |
    +-> result[name] = repr_str
    |
    v
Return: dict[str, str]
```

---

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| repr() raises exception | Use fallback string, continue |
| repr() returns huge string | Truncate to MAX_REPR_LENGTH |
| SnapshotStore.save fails | Log warning, continue to original hook |
| Entire capture fails | Log warning, call original hook |
| KeyboardInterrupt / SystemExit | Skip capture, call original hook only |
| Module imported multiple times | Idempotent, no re-installation |
