"""Python runtime tracker - automatic exception capture to ESF snapshots.

Importing this module installs a sys.excepthook override that captures
uncaught exceptions as ESF snapshots in ~/.errordog/snapshots/.

Usage:
    import errordog.tracker  # hook is active immediately
"""

import logging
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from errordog.models import ErrorSnapshot, Frame, generate_error_id
from errordog.store import SnapshotStore

logger = logging.getLogger(__name__)

MAX_FRAMES: int = 50
MAX_REPR_LENGTH: int = 1000

_installed: bool = False
_original_excepthook = sys.excepthook


def _safe_repr(value: object) -> str:
    """Safely repr() a value with truncation."""
    try:
        repr_str = repr(value)
    except Exception:
        repr_str = f"<unrepresentable: {type(value).__name__}>"
    if len(repr_str) > MAX_REPR_LENGTH:
        repr_str = repr_str[:MAX_REPR_LENGTH] + "..."
    return repr_str


def _serialize_locals(f_locals: dict) -> dict[str, str]:
    """Serialize frame locals to dict[str, str] via safe repr."""
    return {str(name): _safe_repr(value) for name, value in f_locals.items()}


def _extract_frames(tb: types.TracebackType | None) -> list[Frame]:
    """Walk traceback and extract Frame objects, innermost first."""
    frames: list[Frame] = []
    current = tb
    while current is not None:
        frame = current.tb_frame
        raw_path = frame.f_code.co_filename
        if raw_path.startswith("<"):
            file_path = raw_path  # e.g. <frozen runpy>, <string>
        else:
            file_path = str(Path(raw_path).resolve())
        frames.append(
            Frame(
                file_path=file_path,
                line_number=current.tb_lineno,
                function_name=frame.f_code.co_name,
                locals=_serialize_locals(frame.f_locals),
            )
        )
        current = current.tb_next

    # Reverse so innermost (crash point) is first
    frames.reverse()

    # Limit to MAX_FRAMES (keep innermost)
    if len(frames) > MAX_FRAMES:
        frames = frames[:MAX_FRAMES]

    return frames


def _errordog_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: types.TracebackType | None,
) -> None:
    """Errordog excepthook: capture snapshot, then call original hook."""
    # Skip non-error exits
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        _original_excepthook(exc_type, exc_value, exc_tb)
        return

    try:
        frames = _extract_frames(exc_tb)
        if not frames:
            frames = [
                Frame(
                    file_path="<unknown>",
                    line_number=1,
                    function_name="<unknown>",
                    locals={},
                )
            ]

        snapshot = ErrorSnapshot(
            error_id=generate_error_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            exception_type=exc_type.__name__,
            exception_message=str(exc_value),
            frames=frames,
            cwd=str(Path.cwd()),
        )

        store = SnapshotStore()
        path = store.save_snapshot(snapshot)
        logger.info("Errordog snapshot saved: %s", path)
        print(
            f"\n[errordog] Snapshot captured: {snapshot.error_id}",
            file=sys.stderr,
        )
    except Exception:
        logger.warning("Errordog: failed to capture snapshot", exc_info=True)

    _original_excepthook(exc_type, exc_value, exc_tb)


def _install() -> None:
    """Install the errordog excepthook (idempotent)."""
    global _installed
    if _installed:
        return
    sys.excepthook = _errordog_excepthook
    _installed = True


# Auto-activate on import
_install()
