"""Tests for errordog.dap.session — DebugSession domain entities."""

from errordog.dap.session import DebugSession, StackFrame, Variable


class TestStackFrame:
    def test_required_fields(self) -> None:
        f = StackFrame(id=0, name="main", line=42)
        assert f.id == 0
        assert f.name == "main"
        assert f.line == 42
        assert f.source_path is None

    def test_with_source_path(self) -> None:
        f = StackFrame(id=1, name="process", line=10, source_path="/app/main.py")
        assert f.source_path == "/app/main.py"


class TestVariable:
    def test_defaults(self) -> None:
        v = Variable(name="x", value="42")
        assert v.name == "x"
        assert v.value == "42"
        assert v.type is None
        assert v.variables_reference == 0

    def test_with_type(self) -> None:
        v = Variable(name="items", value="[1, 2, 3]", type="list", variables_reference=5)
        assert v.type == "list"
        assert v.variables_reference == 5


class TestDebugSession:
    def test_proxy_mode_defaults(self) -> None:
        s = DebugSession()
        assert s.mode == "proxy"
        assert s.thread_id is None
        assert s.frame_id is None
        assert s.stack_trace == []
        assert s.variables == {}
        assert s.error_id is None

    def test_mock_mode(self) -> None:
        s = DebugSession(mode="mock", error_id="err_abc")
        assert s.mode == "mock"
        assert s.error_id == "err_abc"

    def test_state_mutation(self) -> None:
        s = DebugSession()
        s.thread_id = 3
        s.stack_trace = [StackFrame(id=0, name="foo", line=1)]
        s.variables[0] = [Variable(name="x", value="1")]

        assert s.thread_id == 3
        assert len(s.stack_trace) == 1
        assert len(s.variables[0]) == 1
