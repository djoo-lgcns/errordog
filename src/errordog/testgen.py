"""Template-based reproduction test generation from ESF snapshots."""

import ast
import os
from pathlib import Path

from errordog.models import ErrorSnapshot, Frame
from errordog.store import SnapshotStore

GENERATED_TESTS_DIR = Path.home() / ".errordog" / "generated_tests"


def _select_target_frame(snapshot: ErrorSnapshot) -> Frame:
    """Pick the best frame for test generation (prefer named function over <module>)."""
    frame = snapshot.frames[0]
    if frame.function_name == "<module>" and len(snapshot.frames) > 1:
        frame = snapshot.frames[1]
    return frame


def _derive_module(frame: Frame, cwd: str | None) -> str | None:
    """Convert a frame's file_path to a dotted module path relative to cwd."""
    if not cwd or not frame.file_path.startswith(cwd):
        return None
    rel = os.path.relpath(frame.file_path, cwd)
    if rel.startswith(".."):
        return None
    return rel.replace(os.sep, ".").removesuffix(".py")


def _reconstruct_arg_source(name: str, repr_str: str) -> str:
    """Generate a source-code assignment line for a local variable."""
    try:
        ast.literal_eval(repr_str)
        return f"    {name} = {repr_str}"
    except (ValueError, SyntaxError):
        return f"    {name} = {repr_str!r}  # unparseable, raw repr"


def _render_test(
    error_id: str,
    function_name: str,
    module: str | None,
    exception_type: str,
    frame: Frame,
) -> str:
    """Render the pytest reproduction test source code."""
    lines: list[str] = ["import pytest"]

    if module:
        lines.append(f"from {module} import {function_name}")
    else:
        lines.append(f"# TODO: adjust import path for {function_name}")

    lines.append("")
    lines.append("")
    lines.append(f"def test_reproduce_{error_id}():")
    lines.append(f'    """Auto-generated reproduction test from errordog snapshot."""')

    arg_names: list[str] = []
    for name, repr_str in frame.locals.items():
        lines.append(_reconstruct_arg_source(name, repr_str))
        arg_names.append(name)

    lines.append(f"    with pytest.raises({exception_type}):")
    if arg_names:
        lines.append(f"        {function_name}({', '.join(arg_names)})")
    else:
        lines.append(f"        {function_name}()")

    lines.append("")
    return "\n".join(lines)


def generate_reproduction_test(
    error_id: str,
    store: SnapshotStore | None = None,
) -> dict:
    """Generate a pytest reproduction test from an ESF snapshot.

    Returns a dict with: error_id, test_code, file_path, function_name,
    exception_type, or error on failure.
    """
    if store is None:
        store = SnapshotStore()

    try:
        snapshot = store.get_snapshot(error_id)
    except (FileNotFoundError, ValueError) as e:
        return {"error": str(e), "error_id": error_id}

    frame = _select_target_frame(snapshot)
    module = _derive_module(frame, snapshot.cwd)

    test_code = _render_test(
        error_id=error_id,
        function_name=frame.function_name,
        module=module,
        exception_type=snapshot.exception_type,
        frame=frame,
    )

    output_dir = GENERATED_TESTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"test_reproduce_{error_id}.py"
    output_path.write_text(test_code, encoding="utf-8")

    return {
        "error_id": error_id,
        "test_code": test_code,
        "file_path": str(output_path),
        "function_name": frame.function_name,
        "exception_type": snapshot.exception_type,
    }
