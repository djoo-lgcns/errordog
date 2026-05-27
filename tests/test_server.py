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
    list_errors,
)


class TestListErrors:
    def test_returns_empty_list(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = list_errors()
        assert result == []

    def test_returns_summaries(self, snapshot_dir: Path) -> None:
        import json
        from errordog.models import ErrorSnapshot, Frame

        snap = ErrorSnapshot(
            error_id="err_list_test_001",
            timestamp="2026-03-10T13:16:00Z",
            exception_type="ValueError",
            exception_message="bad value",
            frames=[Frame(file_path="/app/main.py", line_number=10, function_name="run")],
        )
        (snapshot_dir / f"{snap.error_id}.json").write_text(
            json.dumps(snap.model_dump(), indent=2)
        )
        create_server(snapshot_dir=snapshot_dir)
        result = list_errors()
        assert len(result) == 1
        assert result[0]["error_id"] == snap.error_id
        assert result[0]["exception_type"] == "ValueError"


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

    def test_returns_exception_and_frames(self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_stack_frames(nested_snapshot.error_id)
        assert result["exception_type"] == "TypeError"
        assert result["exception_message"] == "unsupported operand"
        frames = result["stack_frames"]
        assert len(frames) == 2
        assert frames[0]["frame_index"] == 0
        assert frames[0]["function_name"] == "calculate"
        assert frames[0]["line_number"] == 10
        assert frames[1]["frame_index"] == 1
        assert frames[1]["function_name"] == "run"

    def test_returns_error_for_missing_snapshot(self, snapshot_dir: Path) -> None:
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_stack_frames("err_nonexistent")
        assert "error" in result

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

    def test_dap_get_variables_value_is_full_repr(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        """value field always contains the full Python repr — readable without drilling."""
        create_server(snapshot_dir=snapshot_dir)
        result = dap_get_variables(nested_snapshot.error_id, frame_index=0)
        item_var = next(v for v in result if v["name"] == "item")
        # Full repr is always present — 'free' is visible without dap_drill_into
        assert "'price': 'free'" in item_var["value"]

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

    def test_workflow_frames_then_variables_then_drill(
        self, snapshot_dir: Path, nested_snapshot: ErrorSnapshot
    ) -> None:
        """Primary workflow: dap_get_stack_frames → dap_get_variables → dap_drill_into."""
        create_server(snapshot_dir=snapshot_dir)

        # Step 1: exception info + crash frame
        result = dap_get_stack_frames(nested_snapshot.error_id)
        assert result["exception_type"] == "TypeError"
        crash_frame = result["stack_frames"][0]
        assert crash_frame["frame_index"] == 0

        # Step 2: read variables — full repr visible directly
        variables = dap_get_variables(nested_snapshot.error_id, frame_index=0)
        item_var = next(v for v in variables if v["name"] == "item")
        assert "'price': 'free'" in item_var["value"]  # readable without drilling

        # Step 3 (optional): drill for structural expansion
        children = dap_drill_into(nested_snapshot.error_id, item_var["variablesReference"])
        price = next(c for c in children if c["name"] == "price")
        assert price["value"] == "'free'"


class TestCreateServer:
    def test_creates_server_with_custom_dir(self, snapshot_dir: Path) -> None:
        server = create_server(snapshot_dir=snapshot_dir)
        assert server is not None
        assert server.name == "errordog"
