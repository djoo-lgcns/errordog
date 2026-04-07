"""Tests for errordog.dap.mock — MockAdapter DAP responses."""

import asyncio
import json
from pathlib import Path

import pytest

from errordog.dap.mock import MockAdapter
from errordog.dap.protocol import encode_message
from errordog.models import ErrorSnapshot, Frame


# ── helpers ──────────────────────────────────────────────────────────────────


class FakeWriter:
    """Captures write() calls and exposes parsed DAP messages."""

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


def _save_snapshot(snapshot_dir: Path, snapshot: ErrorSnapshot) -> None:
    path = snapshot_dir / f"{snapshot.error_id}.json"
    path.write_text(snapshot.model_dump_json(), encoding="utf-8")


@pytest.fixture()
def snapshot_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "snapshots"
    d.mkdir()
    monkeypatch.setattr("errordog.store.DEFAULT_SNAPSHOT_DIR", d)
    return d


@pytest.fixture()
def sample_snapshot(snapshot_dir: Path) -> ErrorSnapshot:
    snap = ErrorSnapshot(
        error_id="err_test001",
        timestamp="2026-01-01T00:00:00Z",
        exception_type="ValueError",
        exception_message="bad input",
        frames=[
            Frame(
                file_path="/app/main.py",
                line_number=10,
                function_name="process",
                locals={"x": "'hello'", "y": "42"},
            ),
            Frame(
                file_path="/app/util.py",
                line_number=5,
                function_name="helper",
                locals={"items": "[1, 2]"},
            ),
        ],
    )
    _save_snapshot(snapshot_dir, snap)
    return snap


# ── tests ─────────────────────────────────────────────────────────────────────


class TestMockAdapterInitialize:
    def test_initialize_returns_capabilities_and_initialized_event(
        self, snapshot_dir: Path
    ) -> None:
        adapter = MockAdapter("err_test001")
        writer = FakeWriter()
        done = asyncio.run(
            adapter.process(_make_request(1, "initialize"), writer)  # type: ignore[arg-type]
        )
        msgs = writer.messages()
        assert not done
        assert msgs[0]["type"] == "response"
        assert msgs[0]["command"] == "initialize"
        assert msgs[0]["success"] is True
        assert msgs[1]["type"] == "event"
        assert msgs[1]["event"] == "initialized"


class TestMockAdapterAttach:
    def test_attach_valid_error_id_sends_stopped_event(
        self, sample_snapshot: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_test001")
        writer = FakeWriter()
        done = asyncio.run(
            adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), writer)  # type: ignore[arg-type]
        )
        msgs = writer.messages()
        assert not done
        assert msgs[0]["type"] == "response"
        assert msgs[0]["success"] is True
        assert msgs[1]["type"] == "event"
        assert msgs[1]["event"] == "stopped"
        assert msgs[1]["body"]["reason"] == "exception"
        assert msgs[1]["body"]["description"] == "ValueError"

    def test_attach_invalid_error_id_returns_done(self, snapshot_dir: Path) -> None:
        adapter = MockAdapter("err_nonexistent")
        writer = FakeWriter()
        done = asyncio.run(
            adapter.process(_make_request(2, "attach", {"error_id": "err_nonexistent"}), writer)  # type: ignore[arg-type]
        )
        msgs = writer.messages()
        assert done is True
        assert msgs[0]["success"] is False


class TestMockAdapterThreads:
    def test_returns_synthetic_main_thread(self, sample_snapshot: ErrorSnapshot) -> None:
        adapter = MockAdapter("err_test001")
        asyncio.run(adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), FakeWriter()))  # type: ignore[arg-type]
        writer = FakeWriter()
        asyncio.run(adapter.process(_make_request(3, "threads"), writer))  # type: ignore[arg-type]
        msgs = writer.messages()
        threads = msgs[0]["body"]["threads"]
        assert len(threads) == 1
        assert threads[0]["id"] == 1
        assert threads[0]["name"] == "MainThread"


class TestMockAdapterStackTrace:
    def test_returns_frames_from_esf(self, sample_snapshot: ErrorSnapshot) -> None:
        adapter = MockAdapter("err_test001")
        asyncio.run(adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), FakeWriter()))  # type: ignore[arg-type]
        writer = FakeWriter()
        asyncio.run(
            adapter.process(_make_request(3, "stackTrace", {"threadId": 1}), writer)  # type: ignore[arg-type]
        )
        frames = writer.messages()[0]["body"]["stackFrames"]
        assert len(frames) == 2
        assert frames[0]["name"] == "process"
        assert frames[0]["line"] == 10
        assert frames[0]["source"]["path"] == "/app/main.py"


class TestMockAdapterScopes:
    def test_returns_locals_scope_with_frame_id_as_var_ref(
        self, sample_snapshot: ErrorSnapshot
    ) -> None:
        adapter = MockAdapter("err_test001")
        asyncio.run(adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), FakeWriter()))  # type: ignore[arg-type]
        writer = FakeWriter()
        asyncio.run(
            adapter.process(_make_request(3, "scopes", {"frameId": 0}), writer)  # type: ignore[arg-type]
        )
        scopes = writer.messages()[0]["body"]["scopes"]
        assert len(scopes) == 1
        assert scopes[0]["name"] == "Locals"
        assert scopes[0]["variablesReference"] == 0  # frame index 0


class TestMockAdapterVariables:
    def test_returns_locals_for_frame(self, sample_snapshot: ErrorSnapshot) -> None:
        adapter = MockAdapter("err_test001")
        asyncio.run(adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), FakeWriter()))  # type: ignore[arg-type]
        writer = FakeWriter()
        asyncio.run(
            adapter.process(_make_request(3, "variables", {"variablesReference": 0}), writer)  # type: ignore[arg-type]
        )
        variables = writer.messages()[0]["body"]["variables"]
        names = {v["name"] for v in variables}
        assert "x" in names
        assert "y" in names

    def test_second_frame_variables(self, sample_snapshot: ErrorSnapshot) -> None:
        adapter = MockAdapter("err_test001")
        asyncio.run(adapter.process(_make_request(2, "attach", {"error_id": "err_test001"}), FakeWriter()))  # type: ignore[arg-type]
        writer = FakeWriter()
        asyncio.run(
            adapter.process(_make_request(3, "variables", {"variablesReference": 1}), writer)  # type: ignore[arg-type]
        )
        variables = writer.messages()[0]["body"]["variables"]
        names = {v["name"] for v in variables}
        assert "items" in names


class TestMockAdapterDisconnect:
    def test_disconnect_returns_done(self, snapshot_dir: Path) -> None:
        adapter = MockAdapter("err_test001")
        writer = FakeWriter()
        done = asyncio.run(
            adapter.process(_make_request(9, "disconnect"), writer)  # type: ignore[arg-type]
        )
        assert done is True
        assert writer.messages()[0]["command"] == "disconnect"


class TestMockAdapterUnsupported:
    def test_unsupported_command_returns_error_response(self, snapshot_dir: Path) -> None:
        adapter = MockAdapter("err_test001")
        writer = FakeWriter()
        done = asyncio.run(
            adapter.process(_make_request(5, "continue"), writer)  # type: ignore[arg-type]
        )
        assert not done
        msg = writer.messages()[0]
        assert msg["success"] is False
        assert "mock mode" in msg["body"]["error"]["format"]
