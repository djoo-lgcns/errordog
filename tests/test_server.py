"""Tests for MCP server and tools."""

import json
from pathlib import Path

import pytest

from errordog.models import ErrorSnapshot, Frame
from errordog.server import (
    create_server,
    dap_drill_into,
    dap_get_stack_frames,
    dap_get_variables,
    evaluate_expression,
    generate_reproduction_test,
    get_error_details,
    list_errors,
)
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


class TestEvaluateExpression:
    def test_evaluates_expression_against_snapshot(
        self, populated_snapshot_dir: Path
    ) -> None:
        create_server(snapshot_dir=populated_snapshot_dir)
        result = evaluate_expression("x + 1", "err_20260310T131600_a3f2b1")
        assert result["success"] is True
        assert result["result"] == "11"
        assert result["mode"] == "mock"

    def test_returns_error_for_missing_snapshot(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = evaluate_expression("x", "err_nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_returns_error_for_bad_frame_index(
        self, populated_snapshot_dir: Path
    ) -> None:
        create_server(snapshot_dir=populated_snapshot_dir)
        result = evaluate_expression("x", "err_20260310T131600_a3f2b1", frame_index=99)
        assert result["success"] is False
        assert "out of range" in result["error"]

    def test_reports_eval_error(self, populated_snapshot_dir: Path) -> None:
        create_server(snapshot_dir=populated_snapshot_dir)
        result = evaluate_expression("1/0", "err_20260310T131600_a3f2b1")
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]


class TestGenerateReproductionTest:
    @pytest.fixture()
    def snapshot_with_cwd(self, snapshot_dir: Path) -> ErrorSnapshot:
        """Snapshot with cwd set so module derivation works."""
        import json

        snap = ErrorSnapshot(
            error_id="err_testgen_mcp",
            timestamp="2026-01-01T00:00:00Z",
            exception_type="TypeError",
            exception_message="bad type",
            cwd="/project",
            frames=[
                Frame(
                    file_path="/project/app.py",
                    line_number=5,
                    function_name="run",
                    locals={"x": "42"},
                ),
            ],
        )
        path = snapshot_dir / f"{snap.error_id}.json"
        path.write_text(json.dumps(snap.model_dump(), indent=2))
        return snap

    def test_generates_test_via_mcp(
        self,
        snapshot_dir: Path,
        snapshot_with_cwd: ErrorSnapshot,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("errordog.testgen.GENERATED_TESTS_DIR", tmp_path / "gen")
        create_server(snapshot_dir=snapshot_dir)
        result = generate_reproduction_test("err_testgen_mcp")
        assert result["function_name"] == "run"
        assert result["exception_type"] == "TypeError"
        assert "def test_reproduce_err_testgen_mcp" in result["test_code"]
        assert Path(result["file_path"]).exists()

    def test_returns_error_for_missing_snapshot(
        self,
        snapshot_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("errordog.testgen.GENERATED_TESTS_DIR", tmp_path / "gen")
        create_server(snapshot_dir=snapshot_dir)
        result = generate_reproduction_test("err_nonexistent")
        assert "error" in result


class TestDapGetStackFrames:
    @pytest.fixture()
    def nested_snapshot(self, snapshot_dir: Path) -> ErrorSnapshot:
        snap = ErrorSnapshot(
            error_id="err_dap_nested_001",
            timestamp="2026-03-10T13:16:00Z",
            exception_type="TypeError",
            exception_message="unsupported operand",
            cwd="/app",
            frames=[
                Frame(
                    file_path="/app/orders.py",
                    line_number=10,
                    function_name="calculate",
                    locals={
                        "item": "{'price': 'free', 'qty': 1}",
                        "total": "0",
                    },
                ),
                Frame(
                    file_path="/app/main.py",
                    line_number=20,
                    function_name="run",
                    locals={"orders": "[{'price': 1500}, {'price': 'free'}]"},
                ),
            ],
        )
        (snapshot_dir / f"{snap.error_id}.json").write_text(
            json.dumps(snap.model_dump(), indent=2)
        )
        return snap

    def test_returns_frames(self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_stack_frames(nested_snapshot.error_id)
        assert len(result) == 2
        assert result[0]["frame_index"] == 0
        assert result[0]["function_name"] == "calculate"
        assert result[0]["line_number"] == 10
        assert result[1]["frame_index"] == 1
        assert result[1]["function_name"] == "run"

    def test_returns_error_for_missing_snapshot(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_stack_frames("err_nonexistent")
        assert len(result) == 1
        assert "error" in result[0]

    def test_dap_get_variables_returns_locals(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_variables(nested_snapshot.error_id, frame_index=0)
        names = {v["name"] for v in result}
        assert "item" in names
        assert "total" in names

    def test_dap_get_variables_nested_has_reference(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_variables(nested_snapshot.error_id, frame_index=0)
        item_var = next(v for v in result if v["name"] == "item")
        assert item_var["variablesReference"] > 0, "dict local should be drillable"

    def test_dap_drill_into_expands_dict(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=snapshot_dir)
        variables = dap_get_variables(nested_snapshot.error_id, frame_index=0)
        item_var = next(v for v in variables if v["name"] == "item")
        children = dap_drill_into(nested_snapshot.error_id, item_var["variablesReference"])
        child_names = {c["name"] for c in children}
        assert "price" in child_names
        assert "qty" in child_names

    def test_dap_drill_into_unknown_ref_returns_empty(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_drill_into(nested_snapshot.error_id, 99999)
        assert result == []

    def test_dap_get_variables_frame_not_found(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_variables(nested_snapshot.error_id, frame_index=99)
        assert len(result) == 1
        assert "error" in result[0]

    def test_dap_drill_into_missing_snapshot(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_drill_into("err_nonexistent", 1000)
        assert len(result) == 1
        assert "error" in result[0]


class TestCreateServer:
    def test_creates_server_with_custom_dir(self, snapshot_dir: Path) -> None:
        server = create_server(snapshot_dir=snapshot_dir)
        assert server is not None
        assert server.name == "errordog"
