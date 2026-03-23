# Code Generation Plan - Unit 2: Python Runtime Tracker

## Unit Context
- **Unit**: Unit 2 - Python Runtime Tracker
- **Requirements**: FR-2.1 (exception hook), FR-2.2 (stack & memory extraction), FR-2.3 (ESF file storage), FR-2.4 (success criteria)
- **Dependencies**: Unit 1 (models, store)
- **Workspace Root**: /Users/djoo/Projects/debugger-v4
- **Code Location**: /Users/djoo/Projects/debugger-v4/src/errordog/

---

## Generation Steps

### Step 1: Tracker Module (FR-2.1, FR-2.2, FR-2.3)
- [x] Create `src/errordog/tracker.py`
  - Module constants: `MAX_FRAMES = 50`, `MAX_REPR_LENGTH = 1000`
  - `_safe_repr(value)` helper: repr() with try/except fallback + truncation
  - `_serialize_locals(f_locals)` helper: dict[str, str] via _safe_repr
  - `_extract_frames(tb)` helper: walk traceback, extract Frame objects, reverse, limit to MAX_FRAMES
  - `_errordog_excepthook(exc_type, exc_value, exc_tb)`: main hook function
    - Guard: skip KeyboardInterrupt, SystemExit
    - Try: build ErrorSnapshot, save via SnapshotStore
    - Except: log warning
    - Finally: call original excepthook
  - Module-level auto-activation: store original hook, install, set guard flag

### Step 2: Tracker Unit Tests
- [x] Create `tests/test_tracker.py`
  - Test _safe_repr with normal values
  - Test _safe_repr with unrepresentable objects
  - Test _safe_repr truncation at MAX_REPR_LENGTH
  - Test _serialize_locals produces dict[str, str]
  - Test _extract_frames from a real traceback
  - Test _extract_frames respects MAX_FRAMES limit
  - Test _extract_frames ordering (innermost first)
  - Test excepthook creates snapshot file
  - Test excepthook skips KeyboardInterrupt
  - Test excepthook skips SystemExit
  - Test excepthook calls original hook
  - Test excepthook survives internal errors (never crashes)
  - Test idempotent import (no double-hook)

### Step 3: Integration Test Script
- [x] Create `scripts/test_tracker_integration.py`
  - Script that imports errordog.tracker, then raises an intentional error
  - After running, snapshot should appear in ~/.errordog/snapshots/
  - Print confirmation message with snapshot path

### Step 4: Documentation Summary
- [x] Create `aidlc-docs/construction/unit-2-runtime-tracker/code/code-summary.md`
  - List created/modified files
  - Document usage pattern
  - Document configuration constants

---

## File Manifest

| Step | File | Type |
|------|------|------|
| 1 | `src/errordog/tracker.py` | Business logic (new) |
| 2 | `tests/test_tracker.py` | Unit tests (new) |
| 3 | `scripts/test_tracker_integration.py` | Integration test script (new) |
| 4 | `aidlc-docs/.../code-summary.md` | Documentation (new) |
