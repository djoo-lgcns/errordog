# Unit 4 Business Rules — AI Hypothesis Testing

## BR-1: Expression Evaluation Mode Selection

**Rule**: When `evaluate_expression` is called, determine the execution mode:
- **Mock mode**: Default. Load snapshot from store, reconstruct namespace from frame locals.
- **Live mode**: If an active DAP proxy session exists with a connected debugpy, forward the evaluate request via DAP protocol.

**Priority**: Mock mode is always available. Live mode requires an active proxy session.

## BR-2: Namespace Reconstruction (Mock Mode)

**Rule**: For mock evaluation, reconstruct a Python namespace from the frame's `locals` dict:
1. For each `(name, repr_string)` in `frame.locals`:
   - Attempt `ast.literal_eval(repr_string)`
   - On success: inject the parsed value into the namespace
   - On failure: **skip the variable** (do not inject)
2. Track skipped variable names in `unavailable_vars`

**Rationale**: Q7 answer — skip unparseable values silently. Only literal-safe values (int, float, str, list, dict, tuple, set, bool, None) are reconstructable.

## BR-3: Expression Execution Safety

**Rule**: No sandboxing. The expression is evaluated with `eval(expression, namespace)` where namespace contains the reconstructed locals.

**Rationale**: Q2 answer — this is a developer tool (equivalent to a debugger REPL). The user is trusted.

**Constraints**:
- `eval()` only, not `exec()` — expressions return values, statements do not
- If `eval()` raises an exception, capture it and return as error in EvalResult

## BR-4: Live Mode Evaluation

**Rule**: For live evaluation via proxy:
1. Construct a DAP `evaluate` request with the expression and frame_id
2. Forward to the connected debugpy instance
3. Await the DAP response
4. Return the result value from the response body

**Constraint**: If no active proxy session exists, return an error indicating live mode is unavailable.

## BR-5: Test Template Structure

**Rule**: Generated reproduction tests follow this template pattern:
```python
import pytest
from {module} import {function_name}

def test_reproduce_{error_id}():
    """Auto-generated reproduction test from errordog snapshot {error_id}."""
    {arg_assignments}
    with pytest.raises({exception_type}):
        {function_name}({arg_names})
```

**Extraction logic**:
- `function_name`: from top frame (frames[0].function_name)
- `module`: derived from top frame file_path (convert path to module dotted notation)
- `arg_names`: keys from top frame locals that match function parameters
- `arg_assignments`: reconstruct argument values via `ast.literal_eval` on repr strings
- `exception_type`: from snapshot.exception_type

## BR-6: Test Output Location

**Rule**: Generated tests are written to `~/.errordog/generated_tests/`.
- Directory is created if it doesn't exist
- Filename: `test_reproduce_{error_id}.py`
- The test code is also returned in the MCP response so the caller can inspect it

**Rationale**: Q4 answer — staging location avoids polluting the project's test directory.

## BR-7: Snapshot Not Found

**Rule**: If `error_id` does not match any stored snapshot:
- `evaluate_expression`: return EvalResult with success=False, error="Snapshot not found: {error_id}"
- `generate_reproduction_test`: return TestGenerationResult with empty test_code and error in the response

## BR-8: Module Path Derivation

**Rule**: When generating the import statement for the reproduction test:
1. Use `snapshot.cwd` as the project root
2. Compute relative path: `frame.file_path` relative to `cwd`
3. Convert to dotted module path: replace `/` with `.`, strip `.py` suffix
4. If the path cannot be made relative (e.g., stdlib frame), use the function name standalone with a comment noting the import needs manual adjustment

## BR-9: DAP Evaluate in Mock Mode (Post-Mortem)

**Rule**: MockAdapter must handle the DAP `evaluate` command so the IDE debug console works in post-mortem sessions.

**Logic**:
1. Use `frameId` from the request to locate frame variables (already stored in `session.variables`)
2. Reconstruct namespace using the same `_parse_repr()` method already on MockAdapter
3. `eval()` the expression against the namespace
4. Return result with `variablesReference` from `_register()` so the result is drillable

**Rationale**: The original plan specifies "AI가 멈춰있는 상태(Live 또는 Mock)에서 특정 파이썬 표현식을 실행". Post-mortem debugging requires expression evaluation in the IDE, not just via MCP.

**Error handling**: If eval raises, return a successful DAP response with the error message as `result` (same behavior as debugpy/pdb — errors are displayed, not protocol failures).

## BR-10: Top Frame Selection for Test Generation

**Rule**: Use `frames[0]` (innermost/crash frame) as the primary source for test generation.
- If `frames[0].function_name` is `<module>` (top-level script), look at `frames[1]` if available
- If no suitable function frame is found, generate a simpler test that just calls the script entry point
