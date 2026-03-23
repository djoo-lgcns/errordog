# Unit Test Execution - Unit 2: Python Runtime Tracker

## Run Unit 2 Tests Only
```bash
uv run pytest tests/test_tracker.py -v
```

## Run All Tests (Unit 1 + Unit 2)
```bash
uv run pytest -v
```

## Expected Results
- **Unit 2 Tests**: 18 passed, 0 failures
- **All Tests**: 52 passed, 0 failures
- **Test Breakdown**:
  - `test_tracker.py`: 18 tests (safe_repr, serialize_locals, extract_frames, excepthook, idempotent install)

## Integration Test
```bash
uv run python scripts/test_tracker_integration.py
```

**Expected**:
1. Script prints "Snapshots before: N"
2. Script crashes with `ValueError: invalid literal for int() with base 10: 'not_a_number'`
3. Normal traceback is printed (original hook preserved)
4. A new snapshot file appears in `~/.errordog/snapshots/`

**Verify snapshot was captured**:
```bash
uv run python scripts/test_tools_manual.py
```
The new ValueError snapshot should appear at the top of the `list_errors()` output.
