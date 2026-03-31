"""Run user scripts with errordog tracker automatically injected."""

import runpy
import sys

from errordog import tracker as _tracker  # noqa: F401 — ensures excepthook is installed


def run(script: str, args: list[str] | None = None) -> None:
    """Run a Python script with errordog tracker active.

    Replaces sys.argv so the target script sees the correct arguments,
    then executes it via runpy.run_path with __name__ == "__main__".
    Uncaught exceptions are routed through sys.excepthook (the tracker).
    """
    sys.argv = [script, *(args or [])]
    try:
        runpy.run_path(script, run_name="__main__")
    except Exception:
        sys.excepthook(*sys.exc_info())
        sys.exit(1)
