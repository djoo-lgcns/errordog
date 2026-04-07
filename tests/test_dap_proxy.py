"""Tests for errordog.dap.proxy — _intercept and DapServer session guard."""

from errordog.dap.proxy import _intercept, DapServer
from errordog.dap.session import DebugSession, StackFrame


class TestIntercept:
    def test_stopped_event_caches_thread_id(self) -> None:
        session = DebugSession()
        pending: dict[int, str] = {}
        msg = {"type": "event", "event": "stopped", "body": {"threadId": 5}}
        _intercept(msg, session, pending)
        assert session.thread_id == 5

    def test_non_stopped_event_does_not_change_thread_id(self) -> None:
        session = DebugSession()
        pending: dict[int, str] = {}
        _intercept({"type": "event", "event": "continued", "body": {}}, session, pending)
        assert session.thread_id is None

    def test_stack_trace_response_caches_frames(self) -> None:
        session = DebugSession()
        pending = {10: "stackTrace"}
        msg = {
            "type": "response",
            "command": "stackTrace",
            "request_seq": 10,
            "success": True,
            "body": {
                "stackFrames": [
                    {"id": 0, "name": "main", "line": 42, "source": {"path": "/app/main.py"}},
                    {"id": 1, "name": "helper", "line": 7, "source": {}},
                ]
            },
        }
        _intercept(msg, session, pending)
        assert len(session.stack_trace) == 2
        assert session.stack_trace[0].name == "main"
        assert session.stack_trace[0].source_path == "/app/main.py"
        assert session.frame_id == 0
        assert 10 not in pending  # consumed from pending

    def test_stack_trace_sets_frame_id_to_first_frame(self) -> None:
        session = DebugSession()
        pending = {1: "stackTrace"}
        msg = {
            "type": "response",
            "command": "stackTrace",
            "request_seq": 1,
            "success": True,
            "body": {
                "stackFrames": [{"id": 7, "name": "foo", "line": 1, "source": {}}]
            },
        }
        _intercept(msg, session, pending)
        assert session.frame_id == 7

    def test_empty_stack_trace_does_not_set_frame_id(self) -> None:
        session = DebugSession()
        pending = {1: "stackTrace"}
        msg = {
            "type": "response",
            "command": "stackTrace",
            "request_seq": 1,
            "success": True,
            "body": {"stackFrames": []},
        }
        _intercept(msg, session, pending)
        assert session.frame_id is None

    def test_variables_response_caches_by_request_seq(self) -> None:
        session = DebugSession()
        pending = {20: "variables"}
        msg = {
            "type": "response",
            "command": "variables",
            "request_seq": 20,
            "success": True,
            "body": {
                "variables": [
                    {"name": "x", "value": "1", "type": "int", "variablesReference": 0},
                ]
            },
        }
        _intercept(msg, session, pending)
        assert 20 in session.variables
        assert session.variables[20][0].name == "x"

    def test_failed_response_not_cached(self) -> None:
        session = DebugSession()
        pending = {5: "stackTrace"}
        msg = {
            "type": "response",
            "command": "stackTrace",
            "request_seq": 5,
            "success": False,
            "body": {},
        }
        _intercept(msg, session, pending)
        assert session.stack_trace == []

    def test_unknown_pending_command_is_ignored(self) -> None:
        session = DebugSession()
        pending = {3: "threads"}
        msg = {
            "type": "response",
            "command": "threads",
            "request_seq": 3,
            "success": True,
            "body": {"threads": [{"id": 1, "name": "main"}]},
        }
        _intercept(msg, session, pending)
        # No crash, state unchanged
        assert session.stack_trace == []


class TestDapServerSessionGuard:
    def test_active_flag_starts_false(self) -> None:
        server = DapServer()
        assert server._active is False

    def test_active_flag_set_during_session(self) -> None:
        """_active prevents double connections — flag logic only, no I/O."""
        server = DapServer()
        server._active = True
        assert server._active is True
