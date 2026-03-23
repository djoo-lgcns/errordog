"""Shared test fixtures for Errordog tests."""

import json
from pathlib import Path

import pytest

from errordog.models import ErrorSnapshot, Frame


@pytest.fixture
def sample_frame() -> Frame:
    return Frame(
        file_path="/home/user/app/main.py",
        line_number=42,
        function_name="process_data",
        locals={"x": "10", "name": "'hello'"},
    )


@pytest.fixture
def sample_snapshot(sample_frame: Frame) -> ErrorSnapshot:
    return ErrorSnapshot(
        error_id="err_20260310T131600_a3f2b1",
        timestamp="2026-03-10T13:16:00Z",
        exception_type="ValueError",
        exception_message="invalid literal for int() with base 10: 'abc'",
        frames=[sample_frame],
    )


@pytest.fixture
def snapshot_dir(tmp_path: Path) -> Path:
    """Create a temporary snapshot directory."""
    d = tmp_path / "snapshots"
    d.mkdir()
    return d


@pytest.fixture
def populated_snapshot_dir(snapshot_dir: Path, sample_snapshot: ErrorSnapshot) -> Path:
    """Snapshot directory with one valid snapshot file."""
    file_path = snapshot_dir / f"{sample_snapshot.error_id}.json"
    file_path.write_text(json.dumps(sample_snapshot.model_dump(), indent=2))
    return snapshot_dir
