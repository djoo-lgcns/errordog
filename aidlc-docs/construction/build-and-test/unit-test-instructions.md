# Unit Test Execution - Unit 1

## Run Unit Tests

### 1. Execute All Unit Tests
```bash
uv run pytest -v
```

### 2. Execute with Coverage (optional)
```bash
uv run pytest --cov=errordog --cov-report=term-missing -v
```

### 3. Run Specific Test Files
```bash
uv run pytest tests/test_models.py -v    # ESF model tests
uv run pytest tests/test_store.py -v     # Snapshot store tests
uv run pytest tests/test_server.py -v    # MCP server tests
```

## Expected Results
- **Total Tests**: 34
- **Expected**: 34 passed, 0 failures
- **Test Breakdown**:
  - `test_models.py`: 13 tests (Frame, ErrorSnapshot, ErrorSummary, error_id)
  - `test_store.py`: 15 tests (init, save, list, get, summaries, corrupted files)
  - `test_server.py`: 6 tests (list_errors, get_error_details, create_server)

## Fix Failing Tests
If tests fail:
1. Review test output for error details
2. Check if snapshot directory permissions are correct
3. Verify Pydantic version compatibility (>=2.0.0 required)
4. Ensure `uv sync` installed all dependencies
