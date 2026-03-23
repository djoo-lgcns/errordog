"""Tests for ESF domain models."""

import re

import pytest
from pydantic import ValidationError

from errordog.models import ErrorSnapshot, ErrorSummary, Frame, generate_error_id


class TestFrame:
    def test_valid_frame(self, sample_frame: Frame) -> None:
        assert sample_frame.file_path == "/home/user/app/main.py"
        assert sample_frame.line_number == 42
        assert sample_frame.function_name == "process_data"
        assert sample_frame.locals == {"x": "10", "name": "'hello'"}

    def test_frame_defaults_empty_locals(self) -> None:
        frame = Frame(file_path="/app.py", line_number=1, function_name="main")
        assert frame.locals == {}

    def test_frame_rejects_zero_line_number(self) -> None:
        with pytest.raises(ValidationError):
            Frame(file_path="/app.py", line_number=0, function_name="main")

    def test_frame_rejects_negative_line_number(self) -> None:
        with pytest.raises(ValidationError):
            Frame(file_path="/app.py", line_number=-1, function_name="main")


class TestErrorSnapshot:
    def test_valid_snapshot(self, sample_snapshot: ErrorSnapshot) -> None:
        assert sample_snapshot.error_id == "err_20260310T131600_a3f2b1"
        assert sample_snapshot.exception_type == "ValueError"
        assert len(sample_snapshot.frames) == 1

    def test_snapshot_requires_at_least_one_frame(self) -> None:
        with pytest.raises(ValidationError):
            ErrorSnapshot(
                error_id="err_20260310T131600_a3f2b1",
                timestamp="2026-03-10T13:16:00Z",
                exception_type="ValueError",
                exception_message="test",
                frames=[],
            )

    def test_snapshot_allows_empty_exception_message(self) -> None:
        snapshot = ErrorSnapshot(
            error_id="err_20260310T131600_a3f2b1",
            timestamp="2026-03-10T13:16:00Z",
            exception_type="SystemExit",
            exception_message="",
            frames=[Frame(file_path="/app.py", line_number=1, function_name="main")],
        )
        assert snapshot.exception_message == ""

    def test_snapshot_json_round_trip(self, sample_snapshot: ErrorSnapshot) -> None:
        json_str = sample_snapshot.model_dump_json()
        restored = ErrorSnapshot.model_validate_json(json_str)
        assert restored == sample_snapshot

    def test_snapshot_dict_round_trip(self, sample_snapshot: ErrorSnapshot) -> None:
        data = sample_snapshot.model_dump()
        restored = ErrorSnapshot.model_validate(data)
        assert restored == sample_snapshot


class TestErrorSummary:
    def test_from_snapshot(self, sample_snapshot: ErrorSnapshot) -> None:
        summary = ErrorSummary.from_snapshot(sample_snapshot)
        assert summary.error_id == sample_snapshot.error_id
        assert summary.timestamp == sample_snapshot.timestamp
        assert summary.exception_type == sample_snapshot.exception_type
        assert summary.exception_message == sample_snapshot.exception_message
        assert summary.file_path == "/home/user/app/main.py"
        assert summary.line_number == 42
        assert summary.function_name == "process_data"


class TestGenerateErrorId:
    def test_format_matches_pattern(self) -> None:
        error_id = generate_error_id()
        pattern = r"^err_\d{8}T\d{6}_[0-9a-f]{6}$"
        assert re.match(pattern, error_id), f"error_id '{error_id}' doesn't match pattern"

    def test_generates_unique_ids(self) -> None:
        ids = {generate_error_id() for _ in range(100)}
        assert len(ids) == 100

    def test_starts_with_err_prefix(self) -> None:
        error_id = generate_error_id()
        assert error_id.startswith("err_")
