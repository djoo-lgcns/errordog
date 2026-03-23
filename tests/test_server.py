"""Tests for MCP server and tools."""

from pathlib import Path

from errordog.models import ErrorSnapshot
from errordog.server import create_server, get_error_details, list_errors
from errordog.store import SnapshotStore


class TestListErrors:
    def test_returns_empty_list(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = list_errors()
        assert result == []

    def test_returns_summaries(
        self, populated_snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=populated_snapshot_dir)
        result = list_errors()
        assert len(result) == 1
        entry = result[0]
        assert entry["error_id"] == sample_snapshot.error_id
        assert entry["exception_type"] == "ValueError"
        assert entry["file_path"] == "/home/user/app/main.py"
        assert entry["line_number"] == 42
        assert entry["function_name"] == "process_data"


class TestGetErrorDetails:
    def test_returns_full_snapshot(
        self, populated_snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=populated_snapshot_dir)
        result = get_error_details(sample_snapshot.error_id)
        assert result["error_id"] == sample_snapshot.error_id
        assert result["exception_type"] == "ValueError"
        assert len(result["frames"]) == 1
        assert result["frames"][0]["file_path"] == "/home/user/app/main.py"

    def test_returns_error_for_missing_id(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = get_error_details("err_20260310T131600_nonexist")
        assert result["error"] == "Snapshot not found"
        assert result["error_id"] == "err_20260310T131600_nonexist"

    def test_returns_error_for_corrupted_file(self, snapshot_dir: Path) -> None:
        (snapshot_dir / "err_20260310T131600_badone.json").write_text("not json")
        create_server(snapshot_dir=snapshot_dir)
        result = get_error_details("err_20260310T131600_badone")
        assert result["error"] == "Snapshot corrupted"


class TestCreateServer:
    def test_creates_server_with_custom_dir(self, snapshot_dir: Path) -> None:
        server = create_server(snapshot_dir=snapshot_dir)
        assert server is not None
        assert server.name == "errordog"
