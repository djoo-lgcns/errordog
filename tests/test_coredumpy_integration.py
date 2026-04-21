"""Integration tests for coredumpy-backed post-mortem debugging."""

import json
import sys
from pathlib import Path

import coredumpy
import pytest

from errordog.dap.mock import MockAdapter
from errordog.evaluator import eval_expression_coredumpy
from errordog.models import ErrorSnapshot, Frame
from errordog.store import SnapshotStore
from errordog.tracker import _errordog_excepthook


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def dump_dir(tmp_path: Path) -> Path:
    d = tmp_path / "dumps"
    d.mkdir()
    return d


@pytest.fixture()
def snapshot_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "snapshots"
    d.mkdir()
    monkeypatch.setattr("errordog.store.DEFAULT_SNAPSHOT_DIR", d)
    return d


@pytest.fixture()
def coredumpy_dump(dump_dir: Path) -> Path:
    """Create a real coredumpy dump from a controlled exception."""
    dump_path = dump_dir / "err_cd_test.dump"

    # Generate a real dump by capturing a frame
    def faulty():
        items = [{"price": 1500, "qty": "2"}, {"price": 3000, "qty": 1}]
        total = 0
        for item in items:
            total += item["price"] * item["qty"]  # TypeError on "2" * 1500

    try:
        faulty()
    except TypeError:
        tb = sys.exc_info()[2]
        # Walk to innermost frame
        while tb.tb_next:
            tb = tb.tb_next
        coredumpy.dump(tb.tb_frame, path=str(dump_path))

    return dump_path


@pytest.fixture()
def snapshot_with_dump(
    snapshot_dir: Path, coredumpy_dump: Path
) -> ErrorSnapshot:
    """ESF snapshot that references a coredumpy dump."""
    snap = ErrorSnapshot(
        error_id="err_cd_test",
        timestamp="2026-01-01T00:00:00Z",
        exception_type="TypeError",
        exception_message="can't multiply sequence by non-int of type 'int'",
        frames=[
            Frame(
                file_path="/app/main.py",
                line_number=5,
                function_name="faulty",
                locals={"items": "[{'price': 1500, 'qty': '2'}]", "total": "0"},
            ),
        ],
        dump_path=str(coredumpy_dump),
    )
    path = snapshot_dir / f"{snap.error_id}.json"
    path.write_text(json.dumps(snap.model_dump(), indent=2))
    return snap


# ── helpers ──────────────────────────────────────────────────────────────────

import asyncio


class FakeWriter:
    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, data: bytes) -> None:
        self._buf.extend(data)

    async def drain(self) -> None:
        pass

    def messages(self) -> list[dict]:
        data = bytes(self._buf)
        result = []
        while data:
            idx = data.index(b"\r\n\r\n")
            header = data[:idx].decode()
            length = int(header.split("Content-Length: ")[1])
            body = data[idx + 4 : idx + 4 + length]
            result.append(json.loads(body))
            data = data[idx + 4 + length :]
        return result


def _make_request(seq: int, command: str, arguments: dict | None = None) -> dict:
    msg: dict = {"seq": seq, "type": "request", "command": command}
    if arguments is not None:
        msg["arguments"] = arguments
    return msg


# ── evaluator tests ──────────────────────────────────────────────────────────


class TestEvalExpressionCoredumpy:
    def test_eval_against_real_objects(self, coredumpy_dump: Path) -> None:
        result = eval_expression_coredumpy(
            "type(items[0]['qty']).__name__", str(coredumpy_dump), frame_index=0
        )
        assert result["success"] is True
        assert result["result"] == "'str'"
        assert result["unavailable_vars"] == []

    def test_eval_len(self, coredumpy_dump: Path) -> None:
        result = eval_expression_coredumpy(
            "len(items)", str(coredumpy_dump), frame_index=0
        )
        assert result["success"] is True
        assert result["result"] == "2"

    def test_eval_error(self, coredumpy_dump: Path) -> None:
        result = eval_expression_coredumpy(
            "1/0", str(coredumpy_dump), frame_index=0
        )
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    def test_bad_frame_index(self, coredumpy_dump: Path) -> None:
        result = eval_expression_coredumpy(
            "x", str(coredumpy_dump), frame_index=999
        )
        assert result["success"] is False
        assert "out of range" in result["error"]


# ── mock adapter with coredumpy ──────────────────────────────────────────────


class TestMockAdapterCoredumpy:
    def _attach(self, adapter: MockAdapter) -> None:
        asyncio.run(
            adapter.process(
                _make_request(2, "attach", {"error_id": "err_cd_test"}),
                FakeWriter(),  # type: ignore[arg-type]
            )
        )

    def test_loads_coredumpy_frames(
        self, snapshot_with_dump: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_cd_test")
        self._attach(adapter)
        assert adapter._coredumpy_frames is not None
        assert len(adapter._coredumpy_frames) > 0

    def test_stack_trace_from_coredumpy(
        self, snapshot_with_dump: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_cd_test")
        self._attach(adapter)
        writer = FakeWriter()
        asyncio.run(
            adapter.process(
                _make_request(3, "stackTrace", {"threadId": 1}),
                writer,  # type: ignore[arg-type]
            )
        )
        frames = writer.messages()[0]["body"]["stackFrames"]
        # Should have real coredumpy frames (more than just the 1 ESF frame)
        assert len(frames) >= 1
        # Top frame should be 'faulty'
        assert frames[0]["name"] == "faulty"

    def test_variables_from_real_objects(
        self, snapshot_with_dump: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_cd_test")
        self._attach(adapter)
        writer = FakeWriter()
        asyncio.run(
            adapter.process(
                _make_request(3, "variables", {"variablesReference": 0}),
                writer,  # type: ignore[arg-type]
            )
        )
        variables = writer.messages()[0]["body"]["variables"]
        names = {v["name"] for v in variables}
        assert "items" in names

    def test_evaluate_against_real_objects(
        self, snapshot_with_dump: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_cd_test")
        self._attach(adapter)
        writer = FakeWriter()
        asyncio.run(
            adapter.process(
                _make_request(
                    10,
                    "evaluate",
                    {"expression": "type(items[0]['qty']).__name__", "frameId": 0},
                ),
                writer,  # type: ignore[arg-type]
            )
        )
        msg = writer.messages()[0]
        assert msg["success"] is True
        assert msg["body"]["result"] == "'str'"

    def test_evaluate_complex_expression(
        self, snapshot_with_dump: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_cd_test")
        self._attach(adapter)
        writer = FakeWriter()
        asyncio.run(
            adapter.process(
                _make_request(
                    10,
                    "evaluate",
                    {"expression": "items[1]['price']", "frameId": 0},
                ),
                writer,  # type: ignore[arg-type]
            )
        )
        msg = writer.messages()[0]
        assert msg["success"] is True
        assert msg["body"]["result"] == "3000"
