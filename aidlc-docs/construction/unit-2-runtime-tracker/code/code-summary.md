# Code Summary - Unit 2: Python Runtime Tracker

## Created Files

### Application Code

| File | Purpose |
|------|---------|
| `src/errordog/tracker.py` | Auto-activating sys.excepthook override, frame extraction, safe serialization |

### Tests

| File | Coverage |
|------|----------|
| `tests/test_tracker.py` | 18 tests: safe_repr, serialize_locals, extract_frames, excepthook behavior, error safety, idempotent install |

### Scripts

| File | Purpose |
|------|---------|
| `scripts/test_tracker_integration.py` | End-to-end test: intentional ValueError -> snapshot captured -> visible via MCP |

## Usage

```python
import errordog.tracker  # Hook is active immediately

# Any uncaught exception will now be captured as an ESF snapshot
# in ~/.errordog/snapshots/ before the normal traceback prints
```

## Configuration Constants

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_FRAMES` | 50 | Maximum stack frames to capture |
| `MAX_REPR_LENGTH` | 1000 | Max chars per variable repr() before truncation |

## Test Results

- **Unit tests**: 18/18 passed
- **All tests (Unit 1 + 2)**: 52/52 passed
- **Integration test**: Snapshot captured, visible via MCP tools
