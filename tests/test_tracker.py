"""Tests for Python runtime tracker."""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from errordog.tracker import (
    MAX_REPR_LENGTH,
    _errordog_excepthook,
    _extract_frames,
    _safe_repr,
    _serialize_locals,
)


class TestSafeRepr:
    def test_normal_values(self) -> None:
        assert _safe_repr(42) == "42"
        assert _safe_repr("hello") == "'hello'"
        assert _safe_repr([1, 2, 3]) == "[1, 2, 3]"

    def test_unrepresentable_object(self) -> None:
        class BadRepr:
            def __repr__(self) -> str:
                raise RuntimeError("cannot repr")

        result = _safe_repr(BadRepr())
        assert result == "<unrepresentable: BadRepr>"

    def test_truncation(self) -> None:
        long_list = list(range(1000))
        result = _safe_repr(long_list)
        assert len(result) <= MAX_REPR_LENGTH + 3  # +3 for "..."
        assert result.endswith("...")

    def test_short_value_not_truncated(self) -> None:
        result = _safe_repr(42)
        assert not result.endswith("...")


class TestSerializeLocals:
    def test_produces_dict_str_str(self) -> None:
        locals_dict = {"x": 10, "name": "hello", "data": [1, 2]}
        result = _serialize_locals(locals_dict)
        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_values_are_repr(self) -> None:
        result = _serialize_locals({"x": 42, "s": "hello"})
        assert result["x"] == "42"
        assert result["s"] == "'hello'"


class TestExtractFrames:
    def _get_traceback(self) -> types.TracebackType:
        """Generate a real traceback by raising an exception."""
        try:
            self._cause_error()
        except ValueError:
            return sys.exc_info()[2]  # type: ignore[return-value]
        raise AssertionError("Should not reach here")

    def _cause_error(self) -> None:
        x = 42  # noqa: F841
        raise ValueError("test error")

    def test_extracts_frames(self) -> None:
        tb = self._get_traceback()
        frames = _extract_frames(tb)
        assert len(frames) >= 2
        # First frame should be innermost (crash point)
        assert frames[0].function_name == "_cause_error"
        assert frames[0].line_number > 0

    def test_innermost_first(self) -> None:
        tb = self._get_traceback()
        frames = _extract_frames(tb)
        assert frames[0].function_name == "_cause_error"
        assert frames[1].function_name == "_get_traceback"

    def test_captures_locals(self) -> None:
        tb = self._get_traceback()
        frames = _extract_frames(tb)
        crash_frame = frames[0]
        assert "x" in crash_frame.locals
        assert crash_frame.locals["x"] == "42"

    def test_respects_max_frames(self) -> None:
        tb = self._get_traceback()
        with patch("errordog.tracker.MAX_FRAMES", 1):
            frames = _extract_frames(tb)
        assert len(frames) == 1
        # Should keep innermost frame
        assert frames[0].function_name == "_cause_error"

    def test_none_traceback(self) -> None:
        frames = _extract_frames(None)
        assert frames == []


class TestErrordogExcepthook:
    def test_creates_snapshot_file(self, snapshot_dir: Path) -> None:
        with patch("errordog.tracker.SnapshotStore") as MockStore:
            mock_instance = MagicMock()
            MockStore.return_value = mock_instance

            tb = self._make_traceback()
            with patch("errordog.tracker._original_excepthook"):
                _errordog_excepthook(ValueError, ValueError("test"), tb)

            mock_instance.save_snapshot.assert_called_once()
            snapshot = mock_instance.save_snapshot.call_args[0][0]
            assert snapshot.exception_type == "ValueError"
            assert snapshot.exception_message == "test"
            assert len(snapshot.frames) >= 1

    def test_skips_keyboard_interrupt(self) -> None:
        with patch("errordog.tracker.SnapshotStore") as MockStore:
            with patch("errordog.tracker._original_excepthook") as mock_orig:
                _errordog_excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
                MockStore.assert_not_called()
                mock_orig.assert_called_once()

    def test_skips_system_exit(self) -> None:
        with patch("errordog.tracker.SnapshotStore") as MockStore:
            with patch("errordog.tracker._original_excepthook") as mock_orig:
                _errordog_excepthook(SystemExit, SystemExit(0), None)
                MockStore.assert_not_called()
                mock_orig.assert_called_once()

    def test_calls_original_hook(self) -> None:
        with patch("errordog.tracker.SnapshotStore"):
            with patch("errordog.tracker._original_excepthook") as mock_orig:
                tb = self._make_traceback()
                _errordog_excepthook(ValueError, ValueError("test"), tb)
                mock_orig.assert_called_once_with(
                    ValueError, mock_orig.call_args[0][1], tb
                )

    def test_survives_internal_error(self) -> None:
        """Excepthook must never crash, even if snapshot save fails."""
        with patch("errordog.tracker.SnapshotStore") as MockStore:
            MockStore.return_value.save_snapshot.side_effect = OSError("disk full")
            with patch("errordog.tracker._original_excepthook") as mock_orig:
                tb = self._make_traceback()
                # Should not raise
                _errordog_excepthook(ValueError, ValueError("test"), tb)
                # Original hook still called
                mock_orig.assert_called_once()

    def test_handles_none_traceback(self) -> None:
        """Hook should handle None traceback gracefully."""
        with patch("errordog.tracker.SnapshotStore") as MockStore:
            mock_instance = MagicMock()
            MockStore.return_value = mock_instance
            with patch("errordog.tracker._original_excepthook"):
                _errordog_excepthook(ValueError, ValueError("test"), None)
            mock_instance.save_snapshot.assert_called_once()
            snapshot = mock_instance.save_snapshot.call_args[0][0]
            assert len(snapshot.frames) == 1
            assert snapshot.frames[0].file_path == "<unknown>"

    def _make_traceback(self) -> types.TracebackType | None:
        try:
            raise ValueError("test")
        except ValueError:
            return sys.exc_info()[2]


class TestIdempotentInstall:
    def test_import_does_not_double_hook(self) -> None:
        """Importing tracker multiple times should not stack hooks."""
        import errordog.tracker as t

        hook_before = sys.excepthook
        # Force re-import attempt
        t._installed = False
        t._install()
        t._install()  # second call should be no-op
        assert sys.excepthook is hook_before or sys.excepthook is _errordog_excepthook
