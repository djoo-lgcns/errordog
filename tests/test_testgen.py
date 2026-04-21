"""Tests for errordog.testgen — reproduction test generation."""

import json
from pathlib import Path

import pytest

from errordog.models import ErrorSnapshot, Frame
from errordog.store import SnapshotStore
from errordog.testgen import generate_reproduction_test


@pytest.fixture()
def snapshot_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "snapshots"
    d.mkdir()
    monkeypatch.setattr("errordog.store.DEFAULT_SNAPSHOT_DIR", d)
    return d


@pytest.fixture()
def generated_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "generated_tests"
    monkeypatch.setattr("errordog.testgen.GENERATED_TESTS_DIR", d)
    return d


def _save(snapshot_dir: Path, snapshot: ErrorSnapshot) -> None:
    path = snapshot_dir / f"{snapshot.error_id}.json"
    path.write_text(json.dumps(snapshot.model_dump(), indent=2), encoding="utf-8")


class TestGenerateReproductionTest:
    def test_generates_valid_pytest(
        self, snapshot_dir: Path, generated_dir: Path
    ) -> None:
        snap = ErrorSnapshot(
            error_id="err_test_gen001",
            timestamp="2026-01-01T00:00:00Z",
            exception_type="TypeError",
            exception_message="unsupported operand type",
            cwd="/home/user/project",
            frames=[
                Frame(
                    file_path="/home/user/project/orders.py",
                    line_number=5,
                    function_name="calculate_price",
                    locals={"items": "[{'price': 1500, 'qty': '1'}]"},
                ),
            ],
        )
        _save(snapshot_dir, snap)
        store = SnapshotStore(snapshot_dir=snapshot_dir)

        result = generate_reproduction_test("err_test_gen001", store=store)

        assert result["error_id"] == "err_test_gen001"
        assert result["function_name"] == "calculate_price"
        assert result["exception_type"] == "TypeError"
        assert "def test_reproduce_err_test_gen001" in result["test_code"]
        assert "from orders import calculate_price" in result["test_code"]
        assert "pytest.raises(TypeError)" in result["test_code"]
        assert "calculate_price(items)" in result["test_code"]

        output_path = Path(result["file_path"])
        assert output_path.exists()
        assert output_path.read_text() == result["test_code"]

    def test_skips_module_frame_to_named_function(
        self, snapshot_dir: Path, generated_dir: Path
    ) -> None:
        snap = ErrorSnapshot(
            error_id="err_test_gen002",
            timestamp="2026-01-01T00:00:00Z",
            exception_type="ValueError",
            exception_message="bad value",
            cwd="/home/user/project",
            frames=[
                Frame(
                    file_path="/home/user/project/main.py",
                    line_number=14,
                    function_name="<module>",
                    locals={"orders": "[1, 2]"},
                ),
                Frame(
                    file_path="/home/user/project/calc.py",
                    line_number=5,
                    function_name="process",
                    locals={"data": "[1, 2]"},
                ),
            ],
        )
        _save(snapshot_dir, snap)
        store = SnapshotStore(snapshot_dir=snapshot_dir)

        result = generate_reproduction_test("err_test_gen002", store=store)

        assert result["function_name"] == "process"
        assert "from calc import process" in result["test_code"]

    def test_no_cwd_adds_todo_comment(
        self, snapshot_dir: Path, generated_dir: Path
    ) -> None:
        snap = ErrorSnapshot(
            error_id="err_test_gen003",
            timestamp="2026-01-01T00:00:00Z",
            exception_type="RuntimeError",
            exception_message="oops",
            frames=[
                Frame(
                    file_path="/somewhere/else/app.py",
                    line_number=10,
                    function_name="run",
                    locals={},
                ),
            ],
        )
        _save(snapshot_dir, snap)
        store = SnapshotStore(snapshot_dir=snapshot_dir)

        result = generate_reproduction_test("err_test_gen003", store=store)

        assert "# TODO: adjust import path" in result["test_code"]

    def test_snapshot_not_found(
        self, snapshot_dir: Path, generated_dir: Path
    ) -> None:
        store = SnapshotStore(snapshot_dir=snapshot_dir)
        result = generate_reproduction_test("err_nonexistent", store=store)
        assert "error" in result
        assert result["error_id"] == "err_nonexistent"

    def test_output_written_to_generated_dir(
        self, snapshot_dir: Path, generated_dir: Path
    ) -> None:
        snap = ErrorSnapshot(
            error_id="err_test_gen004",
            timestamp="2026-01-01T00:00:00Z",
            exception_type="KeyError",
            exception_message="missing key",
            cwd="/proj",
            frames=[
                Frame(
                    file_path="/proj/svc.py",
                    line_number=3,
                    function_name="lookup",
                    locals={"key": "'abc'"},
                ),
            ],
        )
        _save(snapshot_dir, snap)
        store = SnapshotStore(snapshot_dir=snapshot_dir)

        result = generate_reproduction_test("err_test_gen004", store=store)

        assert str(generated_dir) in result["file_path"]
        assert (generated_dir / "test_reproduce_err_test_gen004.py").exists()
