# Unit 4 Code Generation Plan — AI Hypothesis Testing

This plan is the single source of truth for Code Generation of Unit 4.

## Unit Context

- **Unit**: Phase 4 — AI Hypothesis Testing & Auto-Test Generation
- **Dependencies**: Unit 1 (models, store, server), Unit 3 (MockAdapter, DAP proxy)
- **Functional Design**: `aidlc-docs/construction/unit-4-ai-hypothesis/functional-design/`

## What to Build

1. **Shared evaluator module** — namespace reconstruction + eval logic
2. **MockAdapter DAP `evaluate` handler** — post-mortem expression evaluation in IDE
3. **Test generation module** — template-based pytest reproduction test
4. **MCP tools** — `evaluate_expression` and `generate_reproduction_test` on existing server

## Code Location

- Application code: `src/errordog/` (existing package)
- Tests: `tests/` (existing directory)

---

## Steps

### Step 1: Create `src/errordog/evaluator.py`
- [x] `reconstruct_namespace(frame_locals: dict[str, str]) -> tuple[dict[str, Any], list[str]]`
  - Iterate locals, `ast.literal_eval` each repr string
  - Return (namespace dict, list of unavailable var names)
- [x] `eval_expression(expression: str, frame_locals: dict[str, str]) -> dict`
  - Calls `reconstruct_namespace`, then `eval(expression, {"__builtins__": __builtins__}, namespace)`
  - Returns `{success, result, error, unavailable_vars}`

### Step 2: Tests for evaluator
- [x] `tests/test_evaluator.py`
  - Test reconstruct_namespace with parseable values (int, str, list, dict)
  - Test reconstruct_namespace with unparseable values (skipped)
  - Test eval_expression success (e.g., `len(items)`)
  - Test eval_expression with error (e.g., `1/0`)
  - Test eval_expression with unavailable vars reported
  - Test eval with no sandboxing (import, builtins accessible)

### Step 3: Add DAP `evaluate` handler to MockAdapter
- [x] In `src/errordog/dap/mock.py`, add `elif command == "evaluate":` block
  - Extract `expression` and `frameId` from arguments
  - Get frame variables from `session.variables[frameId]`
  - Reconstruct namespace from variable values via `_parse_repr`
  - `eval()` and return DAP response with `result`, `type`, `variablesReference`
  - On eval error: return success response with error string as result

### Step 4: Tests for MockAdapter evaluate
- [x] In `tests/test_dap_mock.py` (or new test file)
  - Test evaluate simple expression (`len(items)`)
  - Test evaluate expression with error
  - Test evaluate against non-existent frame (error response)
  - Test evaluate result is drillable (variablesReference > 0 for dicts/lists)

### Step 5: Create `src/errordog/testgen.py`
- [x] `generate_reproduction_test(error_id: str, store: SnapshotStore | None = None) -> dict`
  - Load snapshot
  - Select target frame (frames[0], skip `<module>` if possible)
  - Derive module path from file_path relative to cwd
  - Reconstruct args via `ast.literal_eval`
  - Render template
  - Write to `~/.errordog/generated_tests/test_reproduce_{error_id}.py`
  - Return `{error_id, test_code, file_path, function_name, exception_type}`

### Step 6: Tests for testgen
- [x] `tests/test_testgen.py`
  - Test with a normal function frame → generates valid pytest
  - Test with `<module>` top frame → falls back to frames[1]
  - Test with non-derivable module path → includes comment about manual import
  - Test output file is written to correct location
  - Test snapshot not found → error dict

### Step 7: Update `src/errordog/server.py` with MCP tools
- [x] Add `evaluate_expression(expression: str, error_id: str, frame_index: int = 0) -> dict`
  - Mock mode: use `evaluator.eval_expression()` with snapshot frame locals
  - Live mode: (placeholder — needs active proxy session, deferred to integration)
- [x] Add `generate_reproduction_test(error_id: str) -> dict`
  - Delegates to `testgen.generate_reproduction_test()`

### Step 8: Tests for MCP tools
- [x] `tests/test_server.py` (extend existing)
  - Test evaluate_expression via MCP (mock mode)
  - Test evaluate_expression with bad error_id
  - Test generate_reproduction_test via MCP
  - Test generate_reproduction_test with bad error_id

### Step 9: Code generation summary
- [x] Write `aidlc-docs/construction/unit-4-ai-hypothesis/code/summary.md`
