"""Tests for snapshot store."""

import json
from pathlib import Path

import pytest

from errordog.models import ErrorSnapshot, Frame
from errordog.store import SnapshotStore


class TestSnapshotStoreInit:
    def test_creates_directory_on_init(self, tmp_path: Path) -> None:
        d = tmp_path / "new_dir" / "snapshots"
        assert not d.exists()
        SnapshotStore(snapshot_dir=d)
        assert d.exists()

    def test_accepts_existing_directory(self, snapshot_dir: Path) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.snapshot_dir == snapshot_dir


class TestSaveSnapshot:
    def test_saves_valid_json(
        self, snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        path = store.save_snapshot(sample_snapshot)

        assert path.exists()
        assert path.name == f"{sample_snapshot.error_id}.json"

        data = json.loads(path.read_text())
        assert data["error_id"] == sample_snapshot.error_id
        assert data["exception_type"] == "ValueError"

    def test_saved_file_is_valid_snapshot(
        self, snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        path = store.save_snapshot(sample_snapshot)

        data = json.loads(path.read_text())
        restored = ErrorSnapshot.model_validate(data)
        assert restored == sample_snapshot


class TestListSnapshots:
    def test_empty_directory(self, snapshot_dir: Path) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.list_snapshots() == []

    def test_lists_valid_snapshots(
        self, populated_snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        store = SnapshotStore(snapshot_dir=populated_snapshot_dir)
        ids = store.list_snapshots()
        assert sample_snapshot.error_id in ids

    def test_skips_corrupted_files(self, snapshot_dir: Path) -> None:
        (snapshot_dir / "bad_file.json").write_text("not valid json")
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.list_snapshots() == []

    def test_skips_invalid_schema(self, snapshot_dir: Path) -> None:
        (snapshot_dir / "bad_schema.json").write_text('{"foo": "bar"}')
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.list_snapshots() == []


class TestGetSnapshot:
    def test_returns_correct_snapshot(
        self, populated_snapshot_dir: Path, sample_snapshot: ErrorSnapshot
    ) -> None:
        store = SnapshotStore(snapshot_dir=populated_snapshot_dir)
        result = store.get_snapshot(sample_snapshot.error_id)
        assert result == sample_snapshot

    def test_raises_on_missing_id(self, snapshot_dir: Path) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        with pytest.raises(FileNotFoundError, match="Snapshot not found"):
            store.get_snapshot("err_20260310T131600_nonexist")

    def test_raises_on_corrupted_file(self, snapshot_dir: Path) -> None:
        (snapshot_dir / "err_20260310T131600_badone.json").write_text("not json")
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        with pytest.raises(ValueError, match="Snapshot corrupted"):
            store.get_snapshot("err_20260310T131600_badone")


class TestListSummaries:
    def test_empty_directory(self, snapshot_dir: Path) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.list_summaries() == []

    def test_returns_summaries_with_top_frame(
        self, populated_snapshot_dir: Path
    ) -> None:
        store = SnapshotStore(snapshot_dir=populated_snapshot_dir)
        summaries = store.list_summaries()
        assert len(summaries) == 1
        s = summaries[0]
        assert s.error_id == "err_20260310T131600_a3f2b1"
        assert s.file_path == "/home/user/app/main.py"
        assert s.line_number == 42
        assert s.function_name == "process_data"

    def test_sorted_by_timestamp_descending(self, snapshot_dir: Path) -> None:
        frame = Frame(file_path="/app.py", line_number=1, function_name="main")
        older = ErrorSnapshot(
            error_id="err_20260310T100000_aaaaaa",
            timestamp="2026-03-10T10:00:00Z",
            exception_type="TypeError",
            exception_message="older error",
            frames=[frame],
        )
        newer = ErrorSnapshot(
            error_id="err_20260310T120000_bbbbbb",
            timestamp="2026-03-10T12:00:00Z",
            exception_type="ValueError",
            exception_message="newer error",
            frames=[frame],
        )
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        store.save_snapshot(older)
        store.save_snapshot(newer)

        summaries = store.list_summaries()
        assert len(summaries) == 2
        assert summaries[0].error_id == newer.error_id
        assert summaries[1].error_id == older.error_id

    def test_skips_corrupted_files(self, snapshot_dir: Path) -> None:
        (snapshot_dir / "bad.json").write_text("corrupted")
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        assert store.list_summaries() == []
